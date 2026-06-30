import pytest
import sys
import argparse
from unittest.mock import patch
from scant_cli import main

def test_cli_requires_command():
    """Weryfikuje, czy brak komendy wyrzuca błąd i wyjście (exit 2)"""
    with patch.object(sys, 'argv', ['scant_cli.py']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2

def test_cli_scan_requires_project():
    """Weryfikuje, czy komenda scan wymaga argumentu --project"""
    with patch.object(sys, 'argv', ['scant_cli.py', 'scan']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2

def test_cli_runpod_parser():
    """Weryfikuje poprawność parsera dla komendy runpod"""
    test_args = [
        'scant_cli.py', 'runpod',
        '--project', 'test_proj',
        '--remote-path', 's3:bucket',
        '--api-key', 'secret_key',
        '--endpoint-id', 'test_id'
    ]
    with patch.object(sys, 'argv', test_args):
        with patch('scant_cli.runpod_process') as mock_process:
            main()
            mock_process.assert_called_once()
            args = mock_process.call_args[0][0]
            assert args.project == 'test_proj'
            assert args.remote_path == 's3:bucket'
            assert args.api_key == 'secret_key'
            assert args.endpoint_id == 'test_id'
