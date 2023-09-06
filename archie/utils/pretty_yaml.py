# https://stackoverflow.com/a/70423579/22144317


import yaml


class PrettyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)
