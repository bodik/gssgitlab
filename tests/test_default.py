"""gssgitlab tests module"""

import sys
from unittest.mock import patch

from gssgitlab import main as gssgitlab_main


def test_unknown_subcommand():
    """Test unknown subcommand"""

    patch_argv = patch.object(sys, 'argv', ['gssgitlab.py'])

    with patch_argv:
        ret = gssgitlab_main()

    assert ret == 1
