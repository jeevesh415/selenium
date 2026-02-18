# Plan: Enhance BiDi Generator for Full Feature Parity

**TL;DR:** The generator currently produces bare-bones methods (dict construction + `command_builder` call). You need to extend the generator to produce the full enhanced code: custom dataclass methods, smart serialization, response deserialization, parameter validation, and result transformation. We'll add a **post-processing configuration system** rather than modifying CDDL. This keeps CDDL minimal while allowing the generator to inject the complex logic currently in files like [browser.py](py/selenium/webdriver/common/bidi/browser.py).

---

## Python Version Requirements

> **CRITICAL:** All code created for this project MUST be compatible with Python 3.10 or later. Bazel manages its own Python 3.10 environment.

**Rules:**
1. **All generated code** must use Python 3.10+ compatible syntax (e.g., `bool | None` type unions, not `Optional[bool]`)
2. **All code execution in terminal** must use Python 3.10:
   - Use `bazel build` and `bazel test` which automatically use the correct Python 3.10
   - If running Python directly: verify with `python3 --version` (must be 3.10+)
   - Never assume system Python matches Bazel's Python
3. **If you encounter Python version errors** (e.g., "SyntaxError" on union types, or import errors):
   - Check the Python version with `python3 --version`
   - Restart the terminal to ensure clean environment
   - Use `bazel` commands preferentially (they handle versioning correctly)
   - Do not use `python` or `python2` commands

---

## Step 1: Create a Method Enhancement Configuration System

**Purpose:** Define rules for enhancing method generation without modifying CDDL specs.

**What to create:**
- New file: `py/private/bidi_enhancements_manifest.py`
  - Defines enhancement rules for each module (browser, session, script, etc.)
  - Specifies validation logic, transformations, serialization rules, response mapping

**Example structure for manifest:**
```python
ENHANCEMENTS = {
    'browser': {
        'create_user_context': {
            'preprocess': {
                'proxy': 'check_serialize_method'  # detect and use to_bidi_dict() if present
            }
        },
        'get_client_windows': {
            'deserialize': 'ClientWindowInfo',     # Return type for response
            'extract_field': 'clientWindows',      # Nested field to extract from response
        },
        'get_user_contexts': {
            'extract_field': 'userContexts',       # Extract list from response
            'extract_property': 'userContext',     # Extract specific property from list items
        },
        'set_download_behavior': {
            'validate': 'validate_download_behavior',   # Validation function name
            'transform': 'transform_download_params'    # Preprocessing function name
        }
    },
    # ... other modules with enhancements
}

# Custom validation/transformation implementations (referenced by name above)
def validate_download_behavior(allowed, destination_folder):
    if allowed is True and not destination_folder:
        raise ValueError("destination_folder is required when allowed=True")
    if allowed is False and destination_folder:
        raise ValueError("destination_folder should not be provided when allowed=False")

def transform_download_params(allowed, destination_folder):
    # Transform simple parameters into nested structure
    if allowed is True:
        return {"type": "allow", "destinationFolder": destination_folder}
    elif allowed is False:
        return {"type": "deny"}
    else:  # None
        return {"type": "allow"}
```

**Responsibilities:**
- List all modules that have enhanced methods
- For each enhanced method, specify what type of enhancement (validation, transform, deserialize, extract, preprocess)
- Keep references to helper functions that implement the logic
- Include dataclass custom methods (getters) specifications

---

## Step 2: Enhance Generator to Use Enhancement Metadata

**File to modify:** `py/generate_bidi.py` (currently ~624 lines)

**What to add:**
1. **Load enhancement config**
   - New function: `load_enhancements_manifest()` - reads the manifest file
   - Parse enhancement rules and make available to code generation functions

2. **Generate custom dataclass methods**
   - Update `generate_dataclass()` to check manifest for custom getter methods
   - For each method listed, generate like:
     ```python
     def get_client_window(self):
         return self.client_window

     def is_active(self):
         return self.active
     ```

3. **Enhance method body generation**
   - Update `to_python_method()` to:
     - **Before execution:** Insert param preprocessing/validation if specified
     - **After execution:** Insert response deserialization/extraction if specified
     - **During building:** Insert serialization checks (proxy.to_bidi_dict() calls)

4. **Add helper code generation functions**
   - `generate_serialization_check()` - for proxy and similar objects
   - `generate_deserialization()` - instantiate dataclass from response dict
   - `generate_result_extraction()` - extract nested fields from response
   - `generate_validation_code()` - inject validation logic

**Example generated method output (after enhancement):**
```python
def create_user_context(
    self,
    accept_insecure_certs: bool | None = None,
    proxy: Any | None = None,
    unhandled_prompt_behavior: Any | None = None,
) -> Generator[dict, dict, dict]:
    """Execute browser.createUserContext and return the user context ID."""
    # GENERATED: Serialization preprocessing
    if proxy and hasattr(proxy, "to_bidi_dict"):
        proxy = proxy.to_bidi_dict()

    # GENERATED: Standard parameter dict construction
    params = {
        "acceptInsecureCerts": accept_insecure_certs,
        "proxy": proxy,
        "unhandledPromptBehavior": unhandled_prompt_behavior,
    }
    params = {k: v for k, v in params.items() if v is not None}
    cmd = command_builder("browser.createUserContext", params)
    result = self._driver.execute(cmd)
    # GENERATED: Response field extraction
    return result.get("userContext") if "userContext" in result else result
```

> **Note:** The generated code uses Python 3.10+ syntax (e.g., `bool | None` union types). All generator modifications must produce Python 3.10+ compatible code.

---

## Step 3: Update Bazel Rules for Generation

**File to modify:** `py/private/generate_bidi.bzl`

**What to change:**
1. Add new Bazel input: `enhancements_manifest` attribute pointing to enhancement manifest file
2. Pass manifest path to generator binary via command-line flag (e.g., `--enhancements-manifest`)
3. Ensure manifest file is available during generation

**Updated Bazel rule usage:**
```bazel
generate_bidi(
    name = "create-bidi-src",
    cddl_file = "//common/bidi/spec:all.cddl",
    enhancements_manifest = "//py/private:bidi_enhancements_manifest.py",
    generator = ":generate_bidi",
    module_name = "selenium/webdriver/common/bidi",
    spec_version = "1.0",
)
```

---

## Step 4: Add Serialization/Deserialization/Validation Helper Functions

**Where:** Modify `py/generate_bidi.py`

**Add new helper functions:**

```python
def generate_serialization_check(param_name: str, param_type: str) -> str:
    """Generate code to check for to_bidi_dict() method on parameter."""
    snake_param = camel_to_snake(param_name)
    return f"""    if {snake_param} and hasattr({snake_param}, "to_bidi_dict"):
        {snake_param} = {snake_param}.to_bidi_dict()"""

def generate_deserialization(response_field: str, dataclass_name: str, response_var: str = "result") -> str:
    """Generate code to deserialize response dicts into dataclass instances."""
    return f"""    if {response_var} and "{response_field}" in {response_var}:
        items = {response_var}.get("{response_field}", [])
        return [
            {dataclass_name}(**item) if isinstance(item, dict) else item
            for item in items
        ]
    return []"""

def generate_result_extraction(response_field: str, extract_property: str | None = None) -> str:
    """Generate code to extract nested field from response."""
    if extract_property:
        return f"""    if result and "{response_field}" in result:
        items = result.get("{response_field}", [])
        return [
            item.get("{extract_property}")
            for item in items
            if isinstance(item, dict)
        ]
    return []"""
    else:
        return f"""    if result and "{response_field}" in result:
        return result.get("{response_field}", [])
    return []"""

def generate_validation_wrapper(validation_func_name: str, params: dict) -> str:
    """Generate code that calls validation function."""
    param_list = ", ".join(f"{k}={k}" for k in params.keys())
    return f"    {validation_func_name}({param_list})"
```

---

## Step 5: Handle Custom Transformation Logic

**In manifest file:** Reference transformation functions by name

**In generator:** Generate code that builds complex nested structures

**Example for `set_download_behavior`:**

Enhancement manifest specifies:
```python
'set_download_behavior': {
    'transform': 'transform_download_params',  # Function that takes params and returns transformed dict
}
```

Generator produces:
```python
def set_download_behavior(
    self,
    allowed: bool | None = None,
    destination_folder: str | None = None,
    user_contexts: list[Any] | None = None,
):
    """Execute browser.setDownloadBehavior."""
    # GENERATED: Call transformation function
    download_behavior = transform_download_params(allowed, destination_folder)

    params = {
        "downloadBehavior": download_behavior,
        "userContexts": user_contexts,
    }
    params = {k: v for k, v in params.items() if v is not None}
    cmd = command_builder("browser.setDownloadBehavior", params)
    return self._driver.execute(cmd)
```

Where `transform_download_params` is imported from the manifest module or defined in `common.py`.

---

## Step 6: Identify All Enhancements Needed

**Audit current bidi files for all enhancements:**

1. **browser.py:**
   - `ClientWindowInfo` dataclass: Add getters (get_client_window, get_state, get_width, get_height, is_active, get_x, get_y)
   - `create_user_context`: Serialize proxy with to_bidi_dict check; extract userContext from result
   - `get_client_windows`: Deserialize response to ClientWindowInfo objects
   - `get_user_contexts`: Extract userContext IDs from nested structure
   - `set_download_behavior`: Validate params; transform to download_behavior object

2. **Other modules:**
   - Review each for similar patterns
   - Document any module-specific enhancements

3. **common.py:**
   - Keep as-is (non-generated, utility functions)
   - No changes needed

4. **permissions.py:**
   - Keep as-is (non-generated, custom implementation)
   - No changes needed

---

## Step 7: Verify Output Matches Current Code

**Process:**

1. **Generate:** Run `bazel build //py:create-bidi-src` with enhanced generator
   - Bazel automatically uses Python 3.10
2. **Compare:** Diff generated output against current source files
   ```bash
   diff -u ./py/selenium/webdriver/common/bidi/browser.py \
           ./bazel-bin/py/selenium/webdriver/common/bidi/browser.py
   ```
3. **Iterate:** Update enhancement manifest based on diff results
4. **Verify types:** Run type checker to ensure generated code has correct type hints
   - Use `bazel` commands for type checking (manages Python 3.10 environment)
5. **Run tests:** Confirm no test failures with generated code
   - Use `bazel test //py:*bidi*` (automatically uses Python 3.10)

---

## Step 8: Integrate Generated Code

**Once verification complete:**

1. **Update build rules** to use generated files as primary source
2. **Backup current files** (git commit before replacing)
3. **Replace manual bidi files** with generated versions
4. **Verify tests pass** with fully generated code

---

## Implementation Approach: Phased

**Phase 1 (Start here):** browser.py
- Create enhancement manifest with browser module enhancements
- Update generator to handle one enhancement type at a time (e.g., dataclass getters first)
- Generate browser.py and verify against current source
- Iterate until browser.py matches perfectly

**Phase 2:** Other modules
- Apply same pattern to remaining modules (session, script, network, storage, etc.)
- Each module likely has fewer enhancements than browser

**Phase 3:** Testing & finalization
- Full test suite pass
- Type checking pass
- Integration with build system verified

---

## Key Decisions

- **No CDDL changes:** All enhancements driven by post-processing configuration
- **Config-driven:** Single manifest file controls all enhancements, decoupled from generator logic
- **Backward compatible:** Enhanced generator still produces valid, working code
- **Iterative:** One module at a time to catch issues early
- **Python 3.10+:** All generated code must use Python 3.10+ syntax; all code execution uses Python 3.10
- **Python format for manifest:** Easier to reference functions, validate syntax, add documentation

---

## Questions to Resolve

1. **Start with browser.py or full manifest?**
   - Recommended: Start with browser.py to prove approach

2. **Dataclass getters strategy:**
   - Auto-generate for all fields, or only specific ones?
   - Recommended: Only those that match current code (specific set)

3. **Transformation functions location:**
   - In enhance manifest file itself, or in common.py?
   - Recommended: Create new file `py/selenium/webdriver/common/bidi/transforms.py` for complex logic
   - Import and reference from manifest

4. **Backward compatibility:**
   - Keep current files as fallback, or full switch-over?
   - Recommended: Full switch-over once verified; build system manages transition

---

## Success Criteria

✓ Generated code uses Python 3.10+ compatible syntax (union types, etc.)
✓ All Copilot-created code verified to work with Python 3.10
✓ Generation uses Python 3.10 (via `bazel build`)
✓ Generated browser.py matches current browser.py (byte-for-byte or close enough)
✓ Generated session.py matches current session.py
✓ All 9 generated modules have enhanced methods where appropriate
✓ Tests pass with fully generated code (via `bazel test` with Python 3.10)
✓ Type checker finds no issues
✓ Can run `bazel build //py:create-bidi-src` and replace all bidi files in one shot
✓ No manual hand-editing of bidi files needed for new spec versions (just regenerate)
