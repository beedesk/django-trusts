import unittest
import runtests

def my_module_suite():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(runtests)
    return suite

