# Install

indianfinance needs **Python 3.12 or newer**. Its only runtime dependency is `httpx`.

!!! note "0.1.0 is not on PyPI yet"

    `pip install indianfinance` currently installs 0.0.2, the old API that 0.1.0
    removes. Until 0.1.0 is released, install from GitHub:

    === "pip"

        ```bash
        pip install "git+https://github.com/samantamrityunjay/indianfinance"
        ```

    === "uv"

        ```bash
        uv add "git+https://github.com/samantamrityunjay/indianfinance"
        ```

## Install the package

=== "pip"

    ```bash
    pip install indianfinance
    ```

=== "uv"

    ```bash
    uv add indianfinance
    ```

## Optional: pandas support

The `[pandas]` extra also installs pandas, for the DataFrame helpers that arrive later
in 0.1.0.

=== "pip"

    ```bash
    pip install "indianfinance[pandas]"
    ```

=== "uv"

    ```bash
    uv add "indianfinance[pandas]"
    ```

## Check the installed version

```python
import indianfinance

print(indianfinance.__version__)
```

For a development install from GitHub this prints:

```text
0.1.0.dev0
```
