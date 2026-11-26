## Exception syntax

We're using at least Python version 3.14.

The following:

```python
except ValueError, RuntimeError:
```

Without parentheses, is valid Python 3.14 syntax per PEP 758, see <https://docs.python.org/3/reference/compound_stmts.html#try>

Do not flag or "fix" it.

The only caveat: parentheses are still required when using as — e.g.

```python
except (ValueError, RuntimeError) as e:
```
