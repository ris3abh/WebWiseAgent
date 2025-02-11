# Can you tell me more about this error: shutil not found

## Sources
1. https://github.com/pyinstaller/pyinstaller/issues/4212
2. https://github.com/pyinstaller/pyinstaller/issues/4794

## Answer
The error "shutil not found" typically indicates that the Python module `shutil`, which is a standard library module used for file operations, is not accessible in the environment where your code is being executed. Here are some key points related to this issue:

- **Standard Library**: The `shutil` module is part of Python's standard library, so it should be available in any standard Python installation. If it is not found, it may indicate an issue with the Python environment or installation.

- **Environment Issues**: This error may arise if your Python environment is not properly configured. For instance, if you're using a virtual environment, ensure that it is activated and that the correct interpreter is being used.

- **PyInstaller Context**: In the context of using PyInstaller, if you're creating an executable from your Python script, you should confirm that the `shutil` module is included in the build process. Sometimes, modules are excluded due to PyInstaller not detecting their usage.

- **Debugging Steps**:
  - Check your Python installation: Ensure that your Python environment is correctly set up and that shutil can be imported in a normal Python script.
  - Re-examine your PyInstaller command: Make sure that the modules you are using are correctly referenced and included in your PyInstaller setup.

- **File Structure**: If the issue persists during the build process, consider reviewing the structure of your project and any hooks you are using, as missing files or incorrect paths in hooks may lead to such errors.

Addressing these aspects should help you diagnose and resolve the "shutil not found" error.