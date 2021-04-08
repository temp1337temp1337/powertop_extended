import os
import csv
import json
import subprocess

# The project is initially deployed here:
# https://github.com/ProgVal/python-powertop/blob/master/powertop/__main__.py
# However, this script was adjusted heavily, as there were several issues with
# the initial deployment and several behaviors resulted in flawed behavior


class Table:
    def __init__(self, header, rows):
        self.header = header
        self._rows = rows

    def rows(self):
        return [dict(zip(self.header, row)) for row in self._rows]

    def __repr__(self):
        return 'Table(header={!r}, rows={!r})'.format(self.header, self._rows)


class Powertop:
    def __init__(self, *, command=('/usr/sbin/powertop', '--quiet'), env=None):
        self.command = tuple(command)
        if env is None:
            env = {}
        env.setdefault('LANG', 'C')
        self.env = env

    def get_measures(self, *, time, iterations=1, section, filename):
        return self._run(time=time, iterations=iterations, section=section, filename=filename)

    def _run(self, *, time, iterations, section, filename):

        arguments = (
                '--csv={}'.format(filename),
                '--time={}'.format(time),
                '--iteration={}'.format(iterations),
                )
        
        # Keep the .csv files under the csv directory
        subprocess.call(self.command + arguments, env=self.env)

        # Convert to json and also return the json objects
        output_list = []
        for report_file in os.listdir('.'):
            if os.path.isfile(report_file):
                if report_file.startswith(filename):

                    with open(report_file, mode='r') as fd:
                        output = fd.readlines()

                    json_output = self._parse_output(output)
                    output_file = ''.join([
                        'json/', report_file.split('.')[0], '.json'])
                    with open(output_file, mode='w+') as fd:
                        json_dump = json.dumps(json_output[section], indent=4)
                        output_list.append(json_dump)
                        fd.write(json_dump)
                    # os.remove(report_file)
        return output_list

    def _parse_output(self, lines):
        (delimiter, version) = self._detect_characteristics(lines)
        sections = self._split_sections(lines)
        d = {name: self._fix_section(name, self._parse_section(section, delimiter=delimiter))
             for (name, section) in sections.items() if section != [[]]}
        if None in d:
            del d[None]
        return d

    @staticmethod
    def _detect_characteristics(lines):
        prefix = 'PowerTOP Version'
        for line in lines:
            if line.startswith(prefix):
                delimiter = line[len(prefix)]
                remainder = line[len(prefix)+1:]
                version = remainder.split(' ', 1)[0]
                # assert version.startswith('v')
                return delimiter, version
        raise ValueError('PowerTOP version/delimiter not found (too recent/old?).')

    @staticmethod
    def _split_sections(lines):
        # TODO: current_table = []
        current_section = []
        section_header = None
        sections = {}
        for line in lines:
            line = line.strip()
            if set(line) == {'_'}:  # all characters are _
                if current_section:
                    if section_header != 'P o w e r T O P':
                        sections[section_header] = current_section
                    section_header = None
                    current_section = []
            elif section_header is None:
                section_header = line.strip(' *')
            else:
                current_section.append(line)
        return sections

    def _parse_section(self, lines, delimiter):
        tables = []
        current_lines = []

        for line in lines:
            if line == '':
                if current_lines:
                    tables.append(self._parse_table(current_lines, delimiter=delimiter))
                    current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            tables.append(self._parse_table(current_lines, delimiter=delimiter))
            # TODO: current_lines = []
        
        return tables

    @staticmethod
    def _parse_table(lines, delimiter):
        data = csv.reader(lines, delimiter=delimiter)
        try:
            header = next(data)
        except StopIteration:
            return None, None
        rows = list(data)
        return Table(header, rows)

    @staticmethod
    def _make_associative(rows):
        d = {}
        for row in rows:
            (key, value) = row
            key = key.strip()
            value = value.strip()
            if key or value:
                d[key] = value
        return d

    def _fix_section(self, name, tables):
        if name == 'System Information':
            results = {}
            for table in tables:
                for row in [table.header] + table._rows:
                    if ':' in row[0]:
                        for item in row:
                            if item.strip() != '':
                                (key, value) = item.split(':')
                                results[key.strip()] = value.strip()
                    else:
                        (key, value) = row  # Will fail if PowerTOP changes its format
                        results[key] = value
            return results
        elif name in ('Processor Idle State Report', 'Processor Frequency Report'):
            if 'Processor Idle State Report':
                cols_per_cpu = 2
            # elif name == 'Processor Frequency Report':
            #    cols_per_cpu = 1
            # else:
            #     assert False
            packages = {}
            # package = None
            cores = {}
            # core = None
            cpus = {}
            # cpu_header = None
            for table in tables:
                if table.header[0] == 'Package':
                    package = table.header[1]
                    packages[package] = self._make_associative(table._rows)
                elif table.header[0].startswith(('Core ', 'GPU ')):
                    core = None
                    for row in [table.header] + table._rows:
                        if row[0] == '' and row[1].startswith(('Core ', 'GPU')):
                            core = row[1].split(' ', 1)[1]
                            cores[core] = {}
                        else:
                            assert core is not None
                            (key, value) = row
                            key = key.strip()
                            value = value.strip()
                            if key or value:
                                cores[core][key] = value
                elif table.header[0] == 'CPU':
                    cpu_header = None
                    for row in [table.header] + table._rows:
                        key = row[0].strip()
                        if key.startswith('CPU'):  # Header
                            if cols_per_cpu == 1:
                                cpu_header = [x[len('CPU '):] for x in row[1:]]
                            elif cols_per_cpu == 2:
                                cpu_header = row[1::2]  # Even-numbered cols
                            else:
                                assert False
                            for cpu in cpu_header:
                                cpus[cpu] = {}
                        elif key:
                            # assert cpu_header
                            for (cpu, percentage, time) in zip(cpu_header, row[0::cols_per_cpu],
                                                               row[1::cols_per_cpu]):
                                cpus[cpu][key] = (percentage.strip(), time.strip())
            return {'packages': packages, 'cores': cores, 'cpus': cpus}
        elif name == 'Optimal Tuned Software Settings':
            return [x[0] for x in tables[0]._rows]
        #  elif name in ('Top 10 Power Consumers', 'Overview of Software Power Consumers',
        #  'Device Power Report', 'Process Device Activity', 'Software Settings in Need of Tuning'):
        else:
            # These sections are clean
            new_tables = []
            for table in tables:
                new_table = list(table.rows())
                new_tables.append(new_table)
            if len(new_tables) == 1:
                return new_tables[0]
            else:
                return new_tables
