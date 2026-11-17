import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from skellyclicker_app import gpu_runtime as gpu


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        sdk = self.root / "sdk"
        library = sdk / ("bin/sl_zed64.dll" if os.name == "nt" else "lib/libsl_zed.so")
        library.parent.mkdir(parents=True)
        library.touch()
        environment = patch.dict(os.environ, {
            "SKELLYCLICKER_GPU_HOME": str(self.root / "workers"),
            "ZED_SDK_ROOT_DIR": str(sdk),
            "SKELLYCLICKER_ZED_SDK_BIN": str(sdk / "bin"),
            "SKELLYCLICKER_TRAINING_PYTHON": "unrelated-training-python",
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_failed_probe_preserves_previous_generation(self):
        with patch.object(gpu.platform, "machine", return_value="x86_64"), \
             patch.object(gpu.sys, "platform", "win32" if os.name == "nt" else "linux"), \
             patch.object(gpu.shutil, "which", return_value="uv"), \
             patch.object(gpu, "run_external"), patch.object(gpu, "check_workers") as check:
            gpu.provision()
            previous = gpu.runtime_config()
            self.assertEqual(check.call_args.args[0]["training_python"], previous["training_python"])
            self.assertNotEqual(previous["training_python"], os.environ["SKELLYCLICKER_TRAINING_PYTHON"])
            (self.root / "workers" / "keep.txt").touch()
            check.side_effect = RuntimeError("probe failed")
            with self.assertRaisesRegex(RuntimeError, "probe failed"):
                gpu.provision()
        self.assertEqual(gpu.runtime_config(), previous)
        generation = json.loads((gpu.runtime_root() / "active.json").read_text())["generation"]
        self.assertEqual({p.name for p in gpu.runtime_root().iterdir()}, {generation, "active.json", "keep.txt"})

    def test_preparation_worker_environment_excludes_frozen_linux_libraries(self):
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/driver",
                                     "PYTHONPATH": "/bundle", "_PYI_PARENT_PROCESS_LEVEL": "1"}), \
             patch.object(gpu.sys, "_MEIPASS", "/bundle", create=True), \
             patch.object(gpu.os, "name", "posix"), patch.object(gpu.subprocess, "Popen") as popen:
            gpu.launch_external(["worker"])
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["LD_LIBRARY_PATH"], "/driver")
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("_PYI_PARENT_PROCESS_LEVEL", env)
