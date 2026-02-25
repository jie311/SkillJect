class SimpleApp:
    def __init__(self):
        self.status = 'active'

    def run(self):
        print('Application is running.')

    def stop(self):
        self.status = 'stopped'
        print('Application stopped.')