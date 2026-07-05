"""AWS SigV4 signer verified against AWS's documented GET ListUsers test vector."""
import hashlib

from clims_core.providers._sigv4 import canonical_request, sign

# AWS docs "Authenticating Requests: Examples" — GET ListUsers
URL = "https://iam.amazonaws.com/?Action=ListUsers&Version=2010-05-08"
AMZ_DATE = "20150830T123600Z"
ACCESS = "AKIDEXAMPLE"
SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
HEADERS = {
    "content-type": "application/x-www-form-urlencoded; charset=utf-8",
    "host": "iam.amazonaws.com",
    "x-amz-date": AMZ_DATE,
}
EXPECTED_CR_HASH = "f536975d06c0309214f805bb90ccff089219ecd68b2577efef23edd43b7e1a59"
EXPECTED_SIGNATURE = "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"


def test_canonical_request_hash_matches_aws_vector():
    cr, signed = canonical_request("GET", URL, HEADERS, b"")
    assert signed == "content-type;host;x-amz-date"
    assert hashlib.sha256(cr.encode()).hexdigest() == EXPECTED_CR_HASH


def test_signature_matches_aws_vector():
    out = sign("GET", URL, "us-east-1", "iam", ACCESS, SECRET,
               {"content-type": "application/x-www-form-urlencoded; charset=utf-8"},
               b"", AMZ_DATE)
    assert EXPECTED_SIGNATURE in out["Authorization"]
    assert out["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
