class StringVar:
    def __init__(self):
        _value = None

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
