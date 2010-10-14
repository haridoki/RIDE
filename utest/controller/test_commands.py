import unittest

from robot.parsing.model import TestCaseFile
from robot.parsing.populators import FromFilePopulator
from robot.utils.asserts import assert_equals

from robotide.controller.filecontroller import TestCaseFileController
from robotide.controller.tablecontrollers import TestCaseController, \
    TestCaseTableController
from robotide.controller.commands import RowAdd, Purify, ChangeCellValue,\
    RowDelete, DeleteRows, ClearArea, PasteArea, InsertCells

STEP1 = '  Step 1  arg'
STEP2 = '  Step 2  a1  a2  a3'
STEP_WITH_COMMENT = '  Foo  # this is a comment'
FOR_LOOP_HEADER = '  : FOR  ${i}  IN  1  2  3'
FOR_LOOP_STEP1 = '    Log  ${i}'

data = ['Test With two Steps',
        STEP1,
        STEP2,
        STEP_WITH_COMMENT,
        FOR_LOOP_HEADER,
        FOR_LOOP_STEP1,
        '  Step bar'+
        '  ${variable}=  some value'
]

def create():
    tcf = TestCaseFile()
    tcf.directory = '/path/to'
    pop = FromFilePopulator(tcf)
    pop.start_table(['Test cases'])
    for row in [ [cell for cell in line.split('  ')] for line in data]:
        pop.add(row)
    pop.eof()
    return tcf


def testcase_controller():
    tcf = create()
    tctablectrl = TestCaseTableController(TestCaseFileController(tcf),
                                          tcf.testcase_table)
    return TestCaseController(tctablectrl, tcf.testcase_table.tests[0])


class TestCaseEditingTest(unittest.TestCase):

    def setUp(self):
        self._steps = None
        self._ctrl = testcase_controller()
        self._ctrl.add_change_listener(self._test_changed)
        self._orig_number_of_steps = len(self._ctrl.steps)
        self._number_of_test_changes = 0

    def test_changing_one_cell(self):
        self._exec(ChangeCellValue(0, 0, 'Changed Step'))
        assert_equals(self._steps[0].keyword, 'Changed Step')

    def test_changing_cell_value_after_last_column_adds_empty_columns(self):
        self._exec(ChangeCellValue(0, 2, 'Hello'))
        assert_equals(self._steps[0].args, ['arg', 'Hello'])

    def test_changing_cell_value_after_last_row_adds_empty_rows(self):
        self._exec(ChangeCellValue(len(data)+5, 0, 'Hello'))
        assert_equals(self._steps[len(data)+5].keyword, 'Hello')

    def test_deleting_row(self):
        self._exec(RowDelete(0))
        assert_equals(len(self._steps), self._orig_number_of_steps-1)
        self._verify_row_does_not_exist(STEP1)

    def test_delete_row_inside_of_for_loop(self):
        self._exec(RowDelete(self._data_row(FOR_LOOP_STEP1)))
        assert_equals(len(self._steps), self._orig_number_of_steps-1)
        self._verify_row_does_not_exist(FOR_LOOP_STEP1)

    def test_delete_for_loop_header_row(self):
        self._exec(RowDelete(self._data_row(FOR_LOOP_HEADER)))
        assert_equals(len(self._steps), self._orig_number_of_steps-1)
        self._verify_row_does_not_exist(FOR_LOOP_HEADER)

    def test_adding_row_last(self):
        self._exec(RowAdd())
        assert_equals(len(self._steps), self._orig_number_of_steps+1)
        assert_equals(self._steps[self._orig_number_of_steps].as_list(), [])
    
    def test_adding_row_first(self):
        self._exec(RowAdd(0))
        assert_equals(len(self._steps), self._orig_number_of_steps+1)
        assert_equals(self._steps[0].as_list(), [])
    
    def test_adding_row_middle(self):
        self._exec(RowAdd(1))
        assert_equals(len(self._steps), self._orig_number_of_steps+1)
        assert_equals(self._steps[1].as_list(), [])

    def test_purify_removes_empty_rows(self):
        self._exec(RowAdd())
        self._exec(RowAdd(1))
        self._exec(RowAdd(2))
        assert_equals(len(self._steps), self._orig_number_of_steps+3)
        self._exec(Purify())
        assert_equals(len(self._steps), self._orig_number_of_steps)

    def test_purify_removes_rows_with_no_data(self):
        self._exec(ChangeCellValue(0,0, ''))
        self._exec(ChangeCellValue(0,1, ''))
        self._exec(Purify())
        assert_equals(len(self._steps), self._orig_number_of_steps-1)

    def test_can_add_values_to_empty_row(self):
        self._exec(RowAdd())
        self._exec(ChangeCellValue(0, 3, 'HELLO'))
        assert_equals(self._steps[0].args, ['arg', '', 'HELLO']) 

    def test_only_comment_is_left(self):
        index = self._data_row(STEP_WITH_COMMENT)
        self._exec(ChangeCellValue(index, 0, ''))
        self._exec(Purify())
        assert_equals(self._steps[index].as_list(), ['# this is a comment'])

    def test_comment_is_changed(self):
        index = self._data_row(STEP_WITH_COMMENT)
        self._exec(ChangeCellValue(index, 1, '# new comment'))
        self._verify_step(index, 'Foo', [], '# new comment')

    def test_cell_value_after_comment_is_changed(self):
        index = self._data_row(STEP_WITH_COMMENT)
        self._exec(ChangeCellValue(index, 2, 'something'))
        assert_equals(self._steps[index].as_list(), ['Foo', '# this is a comment', 'something'])

    def test_change_keyword_value_in_indented_step(self):
        index = self._data_row(FOR_LOOP_STEP1)
        self._exec(ChangeCellValue(index, 1, 'Blog'))
        assert_equals(self._steps[index].keyword, 'Blog')

    def test_delete_multiple_rows(self):
        self._exec(DeleteRows(self._data_row(STEP1), self._data_row(STEP2)))
        assert_equals(len(self._steps), self._orig_number_of_steps-2)
        self._verify_row_does_not_exist(STEP1)
        self._verify_row_does_not_exist(STEP2)
        self._verify_number_of_test_changes(1)

    def test_clear_area(self):
        self._exec(ClearArea((0,1), (1,2)))
        self._verify_step(0, 'Step 1')
        self._verify_step(1, 'Step 2', ['', '', 'a3'])

    def test_paste_area(self):
        self._exec(PasteArea((0, 0), [['Changed Step 1', '', ''],
                                      ['Changed Step 2', '', 'ca2']]))
        self._verify_step(0, 'Changed Step 1')
        self._verify_step(1, 'Changed Step 2', ['', 'ca2', 'a3'])

    def test_insert_cell(self):
        self._exec(InsertCells((0,1), (0,1)))
        self._verify_step(0, 'Step 1', ['', 'arg'])

    def test_inserting_cells_outside_step(self):
        self._exec(InsertCells((0,10), (0,10)))
        self._verify_step(0, 'Step 1', ['arg'])

    def test_insert_cell_before_comment(self):
        self._exec(InsertCells((2,1), (2,1)))
        self._verify_step(2, 'Foo', [''], exp_comment='# this is a comment')

    def test_inserting_many_cells(self):
        self._exec(InsertCells((0,1), (1,2)))
        self._verify_step(0, 'Step 1', ['', '', 'arg'])
        self._verify_step(1, 'Step 2', ['', '', 'a1', 'a2', 'a3'])

    def _data_row(self, line):
        return data.index(line)-1

    def _exec(self, command):
        self._ctrl.execute(command)

    def _test_changed(self, new_test):
        self._number_of_test_changes += 1
        self._steps = new_test.steps

    def _verify_number_of_test_changes(self, expected):
        assert_equals(self._number_of_test_changes, expected)

    def _verify_row_does_not_exist(self, line):
        line_as_list = line.split('  ')[1:]
        for step in self._steps:
            if step.as_list() == line_as_list:
                raise AssertionError('Row "%s" exists' % line)

    def _verify_step(self, index, exp_name, exp_args=[], exp_comment=None):
        exp = [exp_name] + exp_args
        if exp_comment:
            exp += [exp_comment]
        assert_equals(self._steps[index].as_list(), exp)


if __name__ == "__main__":
    unittest.main()