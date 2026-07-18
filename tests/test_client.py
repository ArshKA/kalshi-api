import pytest
from pykalshi.exceptions import (
    AuthenticationError,
    InsufficientFundsError,
    ResourceNotFoundError,
    KalshiAPIError,
    OrderRejectedError,
)


def test_auth_headers_generated(client, mock_response):
    """Verify headers include signature."""
    client._session.request.return_value = mock_response({})

    client.get("/test")

    call_args = client._session.request.call_args
    headers = call_args.kwargs["headers"]
    assert "KALSHI-ACCESS-KEY" in headers
    assert "KALSHI-ACCESS-SIGNATURE" in headers
    assert headers["KALSHI-ACCESS-KEY"] == "fake_key"


def test_handle_success(client, mock_response):
    """Verify successful response returns JSON."""
    client._session.request.return_value = mock_response({"data": "ok"})
    resp = client.get("/test")
    assert resp == {"data": "ok"}


def test_handle_401_raises_auth_error(client, mock_response):
    """Verify 401 raises AuthenticationError."""
    client._session.request.return_value = mock_response(
        {"message": "Unauthorized"}, status_code=401
    )
    with pytest.raises(AuthenticationError):
        client.get("/test")


def test_handle_404_raises_not_found(client, mock_response):
    """Verify 404 raises ResourceNotFoundError."""
    client._session.request.return_value = mock_response(
        {"message": "Not Found"}, status_code=404
    )
    with pytest.raises(ResourceNotFoundError):
        client.get("/test")


def test_insufficient_funds_error(client, mock_response):
    """Verify specific error code raises InsufficientFundsError."""
    client._session.request.return_value = mock_response(
        {"code": "insufficient_funds", "message": "No money"}, status_code=400
    )
    with pytest.raises(InsufficientFundsError):
        client.post("/orders", {})

    # Test alternate code "insufficient_balance"
    client._session.request.return_value = mock_response(
        {"code": "insufficient_balance"}, status_code=400
    )
    with pytest.raises(InsufficientFundsError):
        client.post("/orders", {})


def test_api_error_stores_message(client, mock_response):
    """Verify KalshiAPIError stores the message attribute."""
    client._session.request.return_value = mock_response(
        {"message": "Something went wrong", "code": "bad_request"}, status_code=400
    )
    with pytest.raises(KalshiAPIError) as exc_info:
        client.get("/test")
    assert exc_info.value.message == "Something went wrong"
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "bad_request"


def test_api_error_includes_request_context(client, mock_response):
    """Verify exceptions include request context for debugging."""
    client._session.request.return_value = mock_response(
        {"message": "Bad request", "code": "invalid"}, status_code=400
    )
    with pytest.raises(KalshiAPIError) as exc_info:
        client.get("/markets/KXBTC")

    err = exc_info.value
    assert err.method == "GET"
    assert err.endpoint == "/markets/KXBTC"
    assert err.request_body is None  # GET has no body
    assert err.response_body == {"message": "Bad request", "code": "invalid"}


def test_post_error_includes_request_body(client, mock_response):
    """Verify POST errors include the request body for debugging."""
    order_data = {"ticker": "KXBTC", "action": "buy", "side": "yes", "count": 10}
    client._session.request.return_value = mock_response(
        {"message": "Rejected", "code": "order_rejected"}, status_code=400
    )
    with pytest.raises(OrderRejectedError) as exc_info:
        client.post("/portfolio/events/orders", order_data)

    err = exc_info.value
    assert err.method == "POST"
    assert err.endpoint == "/portfolio/events/orders"
    assert err.request_body == order_data
    assert err.error_code == "order_rejected"


def test_order_rejected_error_codes(client, mock_response):
    """Verify various order rejection codes map to OrderRejectedError."""
    rejection_codes = [
        "order_rejected",
        "market_closed",
        "market_settled",
        "invalid_price",
        "self_trade",
        "post_only_rejected",
    ]
    for code in rejection_codes:
        client._session.request.return_value = mock_response(
            {"message": f"Error: {code}", "code": code}, status_code=400
        )
        with pytest.raises(OrderRejectedError) as exc_info:
            client.post("/portfolio/events/orders", {})
        assert exc_info.value.error_code == code


def test_exception_repr(client, mock_response):
    """Verify exception repr is informative."""
    client._session.request.return_value = mock_response(
        {"message": "Not found"}, status_code=404
    )
    with pytest.raises(ResourceNotFoundError) as exc_info:
        client.get("/markets/INVALID")

    err = exc_info.value
    repr_str = repr(err)
    assert "ResourceNotFoundError" in repr_str
    assert "404" in repr_str
    assert "/markets/INVALID" in repr_str


def test_exception_str_includes_endpoint(client, mock_response):
    """Verify exception string message includes the endpoint."""
    client._session.request.return_value = mock_response(
        {"message": "Auth failed"}, status_code=401
    )
    with pytest.raises(AuthenticationError) as exc_info:
        client.get("/portfolio/balance")

    err_str = str(exc_info.value)
    assert "401" in err_str
    assert "Auth failed" in err_str
    assert "[GET /portfolio/balance]" in err_str
