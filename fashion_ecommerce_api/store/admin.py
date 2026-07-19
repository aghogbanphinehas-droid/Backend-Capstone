from django.contrib import admin
from .models import Category, Brand, Product, ProductVariant, ProductImage

# Registering these simply first
admin.site.register(Category)
admin.site.register(Brand)

# For Products, let's make it look professional by nesting images and variants
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'price', 'stock', 'status')
    list_filter = ('status', 'category', 'brand')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)} # Auto-fills the slug based on the name
    inlines = [ProductVariantInline, ProductImageInline]