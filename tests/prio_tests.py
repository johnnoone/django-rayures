from rayures.prio import PrioritySet


def test_prio_in_order():
    reg = PrioritySet()
    reg.add('key1', 'foo', 10)
    reg.add('key1', 'bar', 20)
    reg.add('key2', 'baz', 30)
    assert reg['key1'] == ['foo', 'bar']


def test_prio_jocker():
    reg = PrioritySet()
    reg.add('key1', 'foo', 10)
    reg.add('*', 'bar', 20)
    reg.add('key2', 'baz', 30)
    assert reg['key1'] == ['foo', 'bar']


def test_prio_match():
    reg = PrioritySet()
    reg.add('key1.sub.alt', 'foo', 10)
    reg.add('key1.*.alt', 'bar', 20)
    reg.add('key2', 'baz', 30)
    assert reg['key1.sub.alt'] == ['foo', 'bar']
