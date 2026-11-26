## Logging exceptions

Always use `loguru.logger.exception` to log exceptions. For example:

```python
  try:
      if df.shape[1] < 2:
          loguru.logger.warning('Cannot compute correlation with fewer than 2 features')
          return None
      return df.corr(method='pearson')
  except Exception as e:
      loguru.logger.exception(f'Failed to compute correlation matrix: {e}')
      raise
```
