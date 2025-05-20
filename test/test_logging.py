import unittest
import logging
from audio_miner.main import RadioRecorder

class TestRadioLogging(unittest.TestCase):

    def test_logger_levels(self):
        recorder = RadioRecorder("http://test", "LoggerTest", verbose=True, use_monitor=False)
        self.assertEqual(recorder.logger.level, logging.DEBUG)

        recorder = RadioRecorder("http://test", "LoggerTest", verbose=False, use_monitor=False)
        self.assertEqual(recorder.logger.level, logging.INFO)

if __name__ == '__main__':
    unittest.main()
