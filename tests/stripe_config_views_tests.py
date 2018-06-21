import json
from rayures.views import stripe_config
view = stripe_config


def test_conf_success(rf, publishable_key):
    request = rf.get('/config')
    response = view(request)
    assert response.status_code == 200
    assert json.loads(response.content) == {"publishable_key": publishable_key}
