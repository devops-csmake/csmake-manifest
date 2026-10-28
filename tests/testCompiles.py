# <copyright>
# (c) Copyright 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCompiles(unittest.TestCase):
    """Guards against Python 2 syntax (print statements, 'except X, e',
    backticks, tab/space mixing) creeping back into any .py file."""

    def test_every_python_file_compiles(self):
        count = 0
        failures = []
        for dirpath, dirnames, filenames in os.walk(REPO):
            dirnames[:] = [d for d in dirnames
                           if d not in ('.git', '__pycache__')]
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                count += 1
                with open(path, 'rb') as f:
                    source = f.read()
                try:
                    compile(source, path, 'exec', dont_inherit=True)
                except (SyntaxError, ValueError) as e:
                    failures.append("%s: %s" % (os.path.relpath(path, REPO), e))
        self.assertGreater(count, 0, "found no .py files under %s" % REPO)
        self.assertEqual([], failures)


if __name__ == '__main__':
    unittest.main()
