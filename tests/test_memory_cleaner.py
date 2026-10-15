import unittest
from contextlib import nullcontext
from assistant.memory_cleaner import clean_memory,summarize,readable_bytes

class FakeMemory:
    def __init__(self,available=(100,600),fail=()):self.available=iter(available);self.fail=fail;self.commands=[]
    def privilege(self):return nullcontext()
    def status(self):return {'total':1000,'available':next(self.available)}
    def operation(self,command):
        self.commands.append(command)
        if command in self.fail:raise OSError('test denied')

class MemoryTests(unittest.TestCase):
    def test_helper_writes_verified_result_without_ui(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from assistant.memory_cleaner import helper_main
        with tempfile.TemporaryDirectory(prefix='xxt-memory-') as folder:
            expected=summarize({'available':1,'total':10},{'available':2,'total':10},['工作集'],[])
            with patch('assistant.memory_cleaner.clean_memory',return_value=expected):self.assertEqual(helper_main([folder,'a'*32]),0)
            payload=json.loads((Path(folder)/'result.json').read_text(encoding='utf-8'));self.assertEqual(payload['nonce'],'a'*32);self.assertEqual(payload['result'],expected)
    def test_helper_error_does_not_write_success(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from assistant.memory_cleaner import helper_main
        with tempfile.TemporaryDirectory(prefix='xxt-memory-') as folder:
            with patch('assistant.memory_cleaner.clean_memory',side_effect=PermissionError('denied')):self.assertEqual(helper_main([folder,'a'*32]),1)
            payload=json.loads((Path(folder)/'result.json').read_text(encoding='utf-8'));self.assertIn('error',payload);self.assertNotIn('result',payload)
    def test_helper_rejects_unscoped_folder(self):
        import tempfile
        from pathlib import Path
        from assistant.memory_cleaner import helper_main
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(helper_main([folder,'a'*32]),2);self.assertFalse((Path(folder)/'result.json').exists())
    def test_cleanup_measures_before_and_after(self):
        fake=FakeMemory();result=clean_memory(fake,lambda _:None)
        self.assertEqual(fake.commands,[2,4]);self.assertEqual(result['released'],500);self.assertEqual(result['after']['available'],600);self.assertEqual(result['status'],'success')
    def test_partial_failures_do_not_cancel_other_operations(self):
        fake=FakeMemory(fail=(2,));result=clean_memory(fake,lambda _:None)
        self.assertEqual(fake.commands,[2,4]);self.assertEqual(result['status'],'partial');self.assertEqual(result['completed'],['待机缓存']);self.assertEqual(len(result['failures']),1)
    def test_all_operations_failed_not_reported_as_success(self):
        result=clean_memory(FakeMemory(fail=(2,4)),lambda _:None);self.assertEqual(result['status'],'failed')
    def test_background_memory_use_never_becomes_negative_release(self):
        result=clean_memory(FakeMemory((600,100)),lambda _:None);self.assertEqual(result['released'],0);self.assertEqual(result['delta'],-500)
    def test_permission_failure_does_not_run_cleaning(self):
        fake=FakeMemory()
        def denied():raise PermissionError('denied')
        fake.privilege=denied
        with self.assertRaises(PermissionError):clean_memory(fake,lambda _:None)
        self.assertEqual(fake.commands,[])
    def test_readable_sizes(self):
        self.assertEqual(readable_bytes(1024**3),'1.00 GB');self.assertEqual(readable_bytes(0),'0.0 MB')
