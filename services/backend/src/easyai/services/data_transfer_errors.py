"""Only application-owned fixed failures may cross the upload API boundary."""

from easyai.domain.data_transfer import TransferError


class TransferFailure(ValueError):
    def __init__(self, code: TransferError):
        self.code = code
        super().__init__(code)


def safe_transfer_error(error: Exception) -> TransferError:
    return error.code if isinstance(error, TransferFailure) else "DATA_TRANSFER_FAILED"
