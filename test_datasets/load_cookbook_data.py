#!/usr/bin/env python
"""
Script to load sample cookbook data without triggering Solr indexing.
This disconnects the parasolr signal handlers before creating records.

Run from the test_datasets/ directory OR from the project root:
    python test_datasets/load_cookbook_data.py
"""
import os
import sys
import django
from pathlib import Path

# Add project root to sys.path so Django can find the ppa package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ppa.settings")
django.setup()

# Import after django.setup() to avoid AppRegistryNotReady
from django.db.models.signals import post_save, pre_delete, m2m_changed  # noqa: E402
from ppa.archive.models import DigitizedWork, Collection  # noqa: E402

# Disconnect ALL signal handlers to prevent Solr indexing
# We need to clear all receivers before creating records
post_save.receivers = []
pre_delete.receivers = []
m2m_changed.receivers = []

print("🔌 Disconnected Solr indexing signals")

# Create a cookbook collection
cookbook_collection, created = Collection.objects.get_or_create(
    name="Historic American Cookbooks", defaults={"exclude": False}
)
print(f"{'✓ Created' if created else '✓ Found'} collection: {cookbook_collection.name}")

# Create sample cookbook entries
cookbooks = [
    {
        "source_id": "cookbook_001",
        "title": "American Cookery",
        "author": "Simmons, Amelia",
        "pub_date": 1798,
        "pub_place": "Hartford, CT",
        "metadata": {
            "ingredients": ["flour", "butter", "eggs", "sugar", "milk"],
            "cook_time": "45 minutes",
            "cuisine": "American Colonial",
            "passage": (
                "Take one pound of flour, half a pound of butter, three eggs well beaten, "
                "and a gill of milk. Mix together and bake in a moderate oven for "
                "forty-five minutes, or until golden brown."
            ),
        },
    },
    {
        "source_id": "cookbook_002",
        "title": "The Frugal Housewife",
        "author": "Carter, Susannah",
        "pub_date": 1803,
        "pub_place": "New York",
        "metadata": {
            "ingredients": ["meat", "vegetables", "herbs", "salt"],
            "cook_time": "2 hours",
            "cuisine": "American",
            "passage": (
                "Take a good piece of meat, wash it well, and put it in a pot with cold water. "
                "Add vegetables, herbs, and salt to taste. Boil gently for two hours until tender."
            ),
        },
    },
    {
        "source_id": "cookbook_003",
        "title": "The Virginia Housewife",
        "author": "Randolph, Mary",
        "pub_date": 1838,
        "pub_place": "Baltimore",
        "metadata": {
            "ingredients": ["cornmeal", "pork", "beans", "molasses"],
            "cook_time": "1 hour",
            "cuisine": "Southern American",
            "passage": (
                "Soak the beans overnight. In the morning, fry the pork until crisp, "
                "then add the beans and cornmeal with enough water to cover. "
                "Sweeten with molasses and simmer for one hour."
            ),
        },
    },
    {
        "source_id": "cookbook_004",
        "title": "The Boston Cooking-School Cook Book",
        "author": "Farmer, Fannie Merritt",
        "pub_date": 1896,
        "pub_place": "Boston",
        "metadata": {
            "ingredients": ["cream", "chocolate", "vanilla", "gelatin"],
            "cook_time": "30 minutes",
            "cuisine": "New England",
            "passage": (
                "Dissolve the gelatin in a little cold water. Melt the chocolate over a gentle "
                "heat, add the cream and vanilla, then stir in the gelatin. Pour into moulds "
                "and set in a cool place for thirty minutes."
            ),
        },
    },
]

for cb_data in cookbooks:
    work, created = DigitizedWork.objects.get_or_create(
        source_id=cb_data["source_id"],
        defaults={
            "title": cb_data["title"],
            "author": cb_data["author"],
            "pub_date": cb_data["pub_date"],
            "pub_place": cb_data["pub_place"],
            "source": DigitizedWork.OTHER,
            "metadata": cb_data["metadata"],
        },
    )
    if not created:
        work.metadata = cb_data["metadata"]
        work.save()
    work.collections.add(cookbook_collection)
    print(f"  {'✓ Created' if created else '✓ Found'}: {work.title} ({work.pub_date})")

print(f"\n✅ Total cookbooks in database: {DigitizedWork.objects.count()}")
print("\n📚 Sample cookbook metadata:")
first_cookbook = DigitizedWork.objects.first()
if first_cookbook:
    print(f"  Title: {first_cookbook.title}")
    print(f"  Ingredients: {first_cookbook.metadata.get('ingredients', [])}")
    print(f"  Cook time: {first_cookbook.metadata.get('cook_time', 'N/A')}")
    print(f"  Cuisine: {first_cookbook.metadata.get('cuisine', 'N/A')}")

print("\n🎯 Adapter Configuration:")
from ppa.adapters.loader import get_adapter  # noqa: E402

adapter = get_adapter()
if adapter:
    print(f"  Name: {adapter.name}")
    print(f"  Display: {adapter.display_name}")
    print(f"  Templates: {adapter.templates_dir}")
else:
    print("  No adapter configured")

print("\n✅ Setup complete! Run 'python manage.py runserver' to start the app.")
