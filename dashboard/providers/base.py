class BaseProvider:
    name = 'base'

    def fetch(self, series, job):
        raise NotImplementedError

    @staticmethod
    def make_observation(series, value, observed_at, previous_value=None,
                         change_label='', status_label='flat'):
        if value is None:
            return None
        try:
            current = float(value)
        except (TypeError, ValueError):
            return None

        previous = None
        if previous_value is not None:
            try:
                previous = float(previous_value)
            except (TypeError, ValueError):
                previous = None

        if status_label == 'flat' and previous is not None:
            if current > previous:
                status_label = 'up'
            elif current < previous:
                status_label = 'down'

        return {
            'value': current,
            'previous_value': previous,
            'observed_at': observed_at,
            'change_label': change_label or '',
            'status_label': status_label,
        }
