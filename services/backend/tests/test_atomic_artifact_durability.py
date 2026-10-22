"""Exercise writable sync, exclusive publication and failure cleanup without torch."""

import builtins
import errno

import pytest

from test_emission import context


@pytest.mark.parametrize("stage", ["success", "fsync", "link", "serializer", "contender"])
def test_atomic_artifact_sync_and_publication(tmp_path, monkeypatch, stage):
    module, runtime = context(tmp_path)
    real_os = module.os
    modes = {}
    operations = []
    destination = runtime.output_root / "outputs/artifact.png"

    def checked_open(path, mode, *args, **kwargs):
        stream = builtins.open(path, mode, *args, **kwargs)
        modes[stream.fileno()] = mode
        return stream

    class CheckedOS:
        def __getattr__(self, name):
            return getattr(real_os, name)

        def fsync(self, descriptor):
            mode = modes[descriptor]
            if not any(flag in mode for flag in "+wax"):
                raise OSError(errno.EBADF, "sync requires a writable handle")
            operations.append("fsync")
            if stage == "fsync":
                raise OSError(errno.EIO, "injected sync failure")
            real_os.fsync(descriptor)

        def link(self, source, target):
            assert operations == ["fsync"]
            operations.append("link")
            if stage == "link":
                raise OSError(errno.EIO, "injected publication failure")
            real_os.link(source, target)

    monkeypatch.setattr(module, "open", checked_open, raising=False)
    monkeypatch.setattr(module, "os", CheckedOS())

    def publish():
        with runtime.atomic_target("outputs/artifact.png") as temporary:
            temporary.write_bytes(b"complete serializer bytes")
            assert not destination.exists()
            if stage == "serializer":
                raise RuntimeError("injected serializer failure")
            if stage == "contender":
                destination.write_bytes(b"other writer")

    try:
        if stage == "success":
            publish()
            assert destination.read_bytes() == b"complete serializer bytes"
            assert operations == ["fsync", "link"]
        else:
            expected = RuntimeError if stage == "serializer" else OSError
            with pytest.raises(expected):
                publish()
            if stage == "contender":
                assert destination.read_bytes() == b"other writer"
            else:
                assert not destination.exists()
        assert list(destination.parent.glob("easyai-part-*")) == []
    finally:
        runtime.close()
