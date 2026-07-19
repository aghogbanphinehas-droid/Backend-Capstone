from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from store.models import Category, Brand, Product, ProductVariant, Review, Wishlist

User = get_user_model()

class StoreCatalogTests(APITestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            email='admin@example.com', username='admin@example.com', password='Password123!', role='ADMIN'
        )
        self.customer_user = User.objects.create_user(
            email='customer@example.com', username='customer@example.com', password='Password123!', role='CUSTOMER'
        )
        
        # Create Category and Brand
        self.category = Category.objects.create(name='Men', slug='men')
        self.brand = Brand.objects.create(name='Zara', description='Fashion brand')
        
        # Create Product
        self.product = Product.objects.create(
            name='Summer T-Shirt',
            slug='summer-t-shirt',
            description='Cool cotton t-shirt',
            category=self.category,
            brand=self.brand,
            sku='TSHIRT-SUM-001',
            price=150.00,
            discount_price=120.00,
            stock=50,
            featured=True,
            status='PUBLISHED',
            created_by=self.admin_user
        )
        
        # Create Variant
        self.variant = ProductVariant.objects.create(
            product=self.product,
            size='XL',
            color='Black',
            stock=20,
            sku='TSHIRT-SUM-001-XL-BLK'
        )

        # URL names
        self.category_list_url = reverse('category-list')
        self.brand_list_url = reverse('brand-list')
        self.product_list_url = reverse('product-list')
        self.variant_list_url = reverse('product-variants-list')
        self.review_list_url = reverse('review-list')
        self.wishlist_list_url = reverse('wishlist-list')

    def test_category_permissions(self):
        """Ensure only Admin can create categories; customers can only view them."""
        # Test anonymous/customer create (should fail)
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.post(self.category_list_url, {'name': 'Shoes'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test admin create (should succeed)
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.category_list_url, {'name': 'Shoes'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_product_filtering_and_search(self):
        """Ensure search and filtering work correctly on products."""
        # Create a second product in a different category, brand and color
        kids_cat = Category.objects.create(name='Kids', slug='kids')
        nike_brand = Brand.objects.create(name='Nike', description='Sportswear')
        second_product = Product.objects.create(
            name='Kids Sneakers',
            slug='kids-sneakers',
            description='Nike sports sneakers',
            category=kids_cat,
            brand=nike_brand,
            sku='SNEAKER-KID-002',
            price=300.00,
            stock=10,
            status='PUBLISHED',
            created_by=self.admin_user
        )
        ProductVariant.objects.create(
            product=second_product,
            size='S',
            color='Blue',
            stock=10,
            sku='SNEAKER-KID-002-S-BLU'
        )

        self.client.force_authenticate(user=self.customer_user)

        # Search by name
        response = self.client.get(f"{self.product_list_url}?search=Sneakers")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Kids Sneakers')

        # Filter by category slug
        response = self.client.get(f"{self.product_list_url}?category__slug=men")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Summer T-Shirt')

        # Filter by color
        response = self.client.get(f"{self.product_list_url}?variants__color=Blue")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Kids Sneakers')

    def test_product_variants_endpoint(self):
        """Ensure product variant endpoints at /api/products/variants/ work."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test GET
        response = self.client.get(self.variant_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Test POST (create variant)
        variant_data = {
            'product': self.product.id,
            'size': 'M',
            'color': 'White',
            'stock': 15,
            'sku': 'TSHIRT-SUM-001-M-WHT'
        }
        response = self.client.post(self.variant_list_url, variant_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProductVariant.objects.count(), 2)

    def test_reviews(self):
        """Ensure authenticated customers can leave reviews and ratings."""
        self.client.force_authenticate(user=self.customer_user)
        review_data = {
            'product': self.product.id,
            'rating': 5,
            'comment': 'Amazing product! Great quality.'
        }
        response = self.client.post(self.review_list_url, review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)
        
        # Non-authenticated cannot leave review
        self.client.logout()
        response = self.client.post(self.review_list_url, review_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wishlist(self):
        """Ensure wishlists allow saving and removing products."""
        self.client.force_authenticate(user=self.customer_user)
        
        # Add to wishlist
        response = self.client.post(self.wishlist_list_url, {'product': self.product.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Wishlist.objects.count(), 1)

        # List wishlist
        response = self.client.get(self.wishlist_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Remove from wishlist
        wishlist_id = response.data[0]['id']
        wishlist_detail_url = reverse('wishlist-detail', args=[wishlist_id])
        response = self.client.delete(wishlist_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Wishlist.objects.count(), 0)
