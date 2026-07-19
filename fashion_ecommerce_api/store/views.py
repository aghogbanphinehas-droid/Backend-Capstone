from django.shortcuts import render
from rest_framework import viewsets, filters, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from .models import Category, Brand, Product, ProductVariant, ProductImage, Review, Wishlist
from .serializers import (
    CategorySerializer, BrandSerializer, ProductSerializer, 
    ProductVariantSerializer, ProductImageSerializer,
    ReviewSerializer, WishlistSerializer
)
from accounts.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAdminOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(status='PUBLISHED')
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'brand__name', 'variants__size', 'variants__color', 'featured']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'created_at']

    def get_queryset(self):
        # Admins can see drafts, customers only see published items
        if self.request.user.is_authenticated and self.request.user.role == 'ADMIN':
            return Product.objects.all()
        return Product.objects.filter(status='PUBLISHED')

    @action(detail=True, methods=['post'], url_path='upload-images')
    def upload_images(self, request, pk=None):
        product = self.get_object()
        files = request.FILES.getlist('images')
        
        if not files:
            return Response({"error": "No images provided"}, status=status.HTTP_400_BAD_REQUEST)
            
        uploaded_images = []
        for file in files:
            img = ProductImage.objects.create(product=product, image=file)
            uploaded_images.append(ProductImageSerializer(img).data)
            
        return Response(uploaded_images, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='toggle-featured')
    def toggle_featured(self, request, pk=None):
        if not request.user.is_authenticated or request.user.role != 'ADMIN':
            return Response({"detail": "Only admins can perform this action."}, status=status.HTTP_403_FORBIDDEN)
        product = self.get_object()
        product.featured = not product.featured
        product.save()
        return Response({"message": f"Product featured status set to {product.featured}"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        if not request.user.is_authenticated or request.user.role != 'ADMIN':
            return Response({"detail": "Only admins can perform this action."}, status=status.HTTP_403_FORBIDDEN)
        product = self.get_object()
        product.status = Product.StatusChoices.PUBLISHED
        product.save()
        return Response({"message": "Product published successfully."}, status=status.HTTP_200_OK)


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAdminOrReadOnly]


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Automatically tie the review to the logged-in user
        serializer.save(user=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own wishlist
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)