from infra.core.interfaces import IOutputFormatter

class SimpleTextOutputFormatter(IOutputFormatter):
    def get_parser(self):
        # Simple parser that just returns the text
        return lambda x: x

    def format(self, data):
        # Simple formatter that just returns the data
        return data
