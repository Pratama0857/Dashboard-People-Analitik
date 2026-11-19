"""Hierarki exception khusus aplikasi (SCPMK-1: penanganan pengecualian)."""


class PeopleAnalyticsError(Exception):
    """Kelas dasar semua galat aplikasi."""


class DataValidationError(PeopleAnalyticsError):
    """Data masukan tidak ada atau tidak memenuhi skema yang diharapkan."""


class ModelError(PeopleAnalyticsError):
    """Model/analisis tidak dapat dijalankan (data kurang, pustaka tidak ada)."""
