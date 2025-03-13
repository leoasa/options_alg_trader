import unittest
import sys
import os
from unittest.runner import TextTestRunner
from unittest.result import TestResult
from colorama import init, Fore, Style

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Initialize colorama for colored output
init()

class CustomTestResult(TestResult):
    """Custom test result class that provides a summary of test results"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)

class CustomTestRunner(TextTestRunner):
    """Custom test runner that uses our custom test result class"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resultclass = CustomTestResult
    
    def run(self, test):
        """Run the test and print a summary of results"""
        result = super().run(test)
        
        # Calculate statistics
        total = result.testsRun
        passed = len(result.successes)
        failed = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)
        
        # Print a summary line
        print("\n" + "="*70)
        print(f"{Fore.CYAN}TEST SUMMARY:{Style.RESET_ALL}")
        print(f"  Total tests: {total}")
        print(f"  {Fore.GREEN}Passed: {passed}{Style.RESET_ALL}")
        if failed > 0:
            print(f"  {Fore.RED}Failed: {failed}{Style.RESET_ALL}")
        if errors > 0:
            print(f"  {Fore.RED}Errors: {errors}{Style.RESET_ALL}")
        if skipped > 0:
            print(f"  {Fore.YELLOW}Skipped: {skipped}{Style.RESET_ALL}")
        
        # Print a success message based on results
        print("\n" + "-"*70)
        if passed == total:
            print(f"{Fore.GREEN}Success! Passed all {total} tests.{Style.RESET_ALL}")
        elif passed > 0:
            print(f"{Fore.YELLOW}Almost there! Passed {passed} out of {total} tests.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}No tests passed yet...{Style.RESET_ALL}")
        print("="*70 + "\n")
        
        return result

def run_tests(test_modules):
    """Run tests from the specified modules and print a summary"""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add tests from each module
    for module in test_modules:
        try:
            tests = loader.loadTestsFromName(module)
            suite.addTest(tests)
        except (ImportError, AttributeError) as e:
            print(f"Error loading tests from {module}: {e}")
    
    # Run the tests with our custom runner
    runner = CustomTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == "__main__":
    # Get test modules from command line arguments or use defaults
    if len(sys.argv) > 1:
        test_modules = sys.argv[1:]
    else:
        test_modules = ["tests.test_options_trading", "tests.test_integration"]
    
    # Run the tests
    result = run_tests(test_modules)
    
    # Set exit code based on test results
    sys.exit(not result.wasSuccessful()) 