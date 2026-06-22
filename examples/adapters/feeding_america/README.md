# Feeding America Historical Cookbooks

Adapter for the Feeding America historical cookbook dataset from MSU

## Configuration

This adapter is configured in `adapter.yaml`.

## Field Mapping

| Solr Field | Model Path |
|------------|------------|
| `title` | `title` |
| `author` | `author` |
| `pub_date` | `pub_date` |
| `pub_place` | `pub_place` |
| `recipes` | `metadata.recipes` |

## Usage

1. Configure in settings:
   ```python
   ARCHIVE_ADAPTER = 'feeding_america'
   ADAPTERS_DIR = BASE_DIR / 'examples' / 'adapters'
   ```

2. Validate:
   ```bash
   python manage.py adapter validate feeding_america
   ```

3. Test:
   ```bash
   python manage.py adapter test feeding_america
   ```

## Template Overrides

Place custom templates in the `templates/` directory. They will override default templates.

## Static Assets

Place custom CSS, JavaScript, and images in the `static/` directory.
