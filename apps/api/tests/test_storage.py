from unittest.mock import Mock

from app.storage import PrivateStorage


def test_storage_operations_use_the_configured_private_bucket() -> None:
    bucket = Mock()
    client = Mock()
    client.storage.from_.return_value = bucket
    bucket.create_signed_url.return_value = {"signedURL": "https://signed.example/file"}
    storage = PrivateStorage(client=client, bucket="editimage")

    storage.upload("sources/project/product.png", b"png", "image/png")
    storage.download("generated/project/base.png")
    url = storage.signed_url("exports/project/final.png", 900)

    assert client.storage.from_.call_count == 3
    client.storage.from_.assert_called_with("editimage")
    bucket.upload.assert_called_once()
    bucket.download.assert_called_once_with("generated/project/base.png")
    assert url == "https://signed.example/file"
