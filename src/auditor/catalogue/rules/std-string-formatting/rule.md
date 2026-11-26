## String formatting

- **Always use f-strings** instead of `%` formatting or `.format()`
- Convert existing `%` patterns to f-strings when editing
- Example: `f'Exception: {e}'` instead of `'Exception: %s' % e`
- Use single quotes for strings whenever possible (enforced by ruff format config)
- Exception: use double quotes when the string itself contains a single quote
