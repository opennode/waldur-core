class BackupError(Exception):
    """
    Base exception for backup errors.
    """
    pass


class BackupStrategyNotFoundError(BackupError):
    """
    Backup strategy for given backup source doest not exist
    """
    pass


class BackupStrategyExecutionError(BackupError):
    pass
