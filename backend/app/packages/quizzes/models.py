"""
Contains models for the Quizzes package
"""
import os
from app.util import db
import subprocess
RUN_CODE_FILE = os.path.join("app", "packages", "quizzes", "run_code.sh")
RUN_CODE_COMMAND = "bash " + RUN_CODE_FILE + " {}"
TIME_LIMIT_EXCEEDED = "ERROR: Time Limit Exceeded"


def get_quizzes(teacher_id):
    """
    Gets all the quizzes that the teacher owns
    """

    query = """
    SELECT quiz_id, quiz_name, quiz_short_desc, quiz_language_id
    FROM quizzes
    WHERE quiz_teacher_id = %s
    """

    quizzes = db.query(query, (teacher_id))

    return quizzes


def get_quiz_instance(qc_id):
    """
    Gets name of a quiz based on the quiz_id
    """

    query = """
    SELECT quizzes_courses.qc_id, quizzes_courses.qc_course_id, quizzes_courses.qc_start_date * 1000 AS qc_start_date, quizzes_courses.qc_end_date * 1000 AS qc_end_date, quizzes.quiz_id, quizzes.quiz_name,quizzes.quiz_language_id, quizzes.quiz_short_desc, teachers.teacher_id
    FROM quizzes_courses
    INNER JOIN quizzes ON quizzes_courses.qc_quiz_id = quizzes.quiz_id
    LEFT JOIN courses ON quizzes_courses.qc_course_id = courses.course_id
    LEFT JOIN teachers ON teachers.teacher_id = courses.course_teacher_id
    WHERE quizzes_courses.qc_id = %s
    """

    quizzes = db.query(query, (qc_id))

    return quizzes[0]


def get_quiz_template(quiz_id):
    """
    Gets name of a quiz based on the quiz_id
    """

    query = """
    SELECT quizzes.quiz_id, quizzes.quiz_name,quizzes.quiz_language_id, quizzes.quiz_short_desc, quizzes.quiz_teacher_id
    FROM quizzes 
    WHERE quizzes.quiz_id = %s
    """

    quizzes = db.query(query, (quiz_id))

    return quizzes[0]


def check_dates(start_date, end_date):
    """
    Returns true if dates are in the right order
    """

    current_date = int(time.time())

    if current_date <= start_date and start_date <= end_date:
        return True
    return False


def check_languages(language):
    """
    Returns true if the language exists in the database
    """

    query = """
    SELECT * FROM languages
    """

    languages = db.query(query)

    exists = False
    for lang in languages:
        if lang.language_id == language:
            exists = True
    return exists


def edit_quiz(quiz_id, name, start_date, end_date, description, language):
    """
    Edits a quiz
    """

    query = """
    UPDATE quizzes
    SET 
    quiz_name = %s,
    quiz_start_date = %s,
    quiz_end_date = %s,
    quiz_short_desc = %s,
    quiz_language_id = %s
    WHERE quiz_id = %s
    """

    db.query(query,
             (name, start_date, end_date, description, language, quiz_id))
    return


def get_questions(quiz_id):
    """
    Gets questions based on quiz id
    """

    query = """
    SELECT *
    FROM questions
    WHERE question_quiz_id = %s
    ORDER BY question_id
    """

    questions = db.query(query, (quiz_id))

    return questions


def get_question_worth(student_answers):
    """
    Returns both the question worth and total negated for a specific question in tuple form .
    Returns None for both values if user hasn't attemped question 
    """

    attempt_dict = {}

    total_left = 10

    if not len(student_answers):
        return None, None, None

    for curr in student_answers:
        if not curr["attempt_id"] in attempt_dict:
            attempt_dict[curr["attempt_id"]] = {"test_case_wrong": False}

        if curr["test_expected"] != curr["answer_content"]:
            if not attempt_dict[curr["attempt_id"]]["test_case_wrong"]:
                total_left -= 1
            attempt_dict[curr["attempt_id"]]["test_case_wrong"] = True

    last_attempt_id = student_answers[-1]["attempt_id"]

    last_attempt_wrong = attempt_dict[last_attempt_id]["test_case_wrong"]

    total_worth = 0.0 if last_attempt_wrong else total_left

    return (total_worth, 10 - total_left, last_attempt_wrong)


def get_mark_worth(question_id, student_id):
    """
    Returns both the marks for the submission and total negated from specific question
    """

    query = """
         SELECT attempts.attempt_id, tests.test_id, tests.test_expected, answers.answer_content
        FROM attempts
        INNER JOIN answers ON attempts.attempt_id = answers.answer_attempt_id
        INNER JOIN tests ON attempts.attempt_question_id = tests.test_question_id
        WHERE attempts.attempt_question_id = %s AND attempts.attempt_student_id = %s
        ORDER BY attempts.attempt_id, tests.test_id
    """

    all_tests = db.query(query, (question_id, student_id))

    question_worth, total_negated, last_attempt_wrong = get_question_worth(
        all_tests)

    return question_worth, total_negated, last_attempt_wrong


def get_tests(questions, student_id):
    """
    Gets question test cases based on quiz id
    """

    for question in questions:
        # Gets all the test cases
        query = """
        SELECT test_id, test_input, test_expected
        FROM tests
        WHERE test_question_id = %s
        """

        test_cases = db.query(query, (question["question_id"]))

        question["test_cases"] = test_cases

        # If user is not student, then don't get answers (because teachers and free trials can't get answers)
        if not student_id:
            continue

        # Gets students answers
        query2 = """
        SELECT answers.answer_id, tests.test_input, tests.test_expected, answers.answer_content AS output
FROM answers
INNER JOIN tests ON answers.answer_test_id = tests.test_id
WHERE answer_attempt_id = (SELECT attempt_id 
							FROM attempts
							WHERE attempt_student_id = %s
							AND attempt_question_id = %s
							ORDER BY attempt_id
							DESC LIMIT 1) 
AND answer_test_id IN (SELECT test_id
					   FROM tests
					   WHERE test_question_id = %s
					   )
        """

        # Used to figure out mark deductions
        query3 = """
        SELECT attempts.attempt_id, tests.test_id, tests.test_expected, answers.answer_content
        FROM attempts
        INNER JOIN answers ON attempts.attempt_id = answers.answer_attempt_id
        INNER JOIN tests ON attempts.attempt_question_id = tests.test_question_id
        WHERE attempts.attempt_question_id = %s AND attempts.attempt_student_id = %s
        ORDER BY attempts.attempt_id, tests.test_id
        """

        # Will return array with all users tests
        all_tests = db.query(query3, (question["question_id"], student_id))

        test_case_results = db.query(
            query2, (student_id, question["question_id"], student_id))

        # Gets the latest test case results
        question["test_case_results"] = test_case_results

        question_worth, total_negated, last_attempt_wrong = get_question_worth(
            all_tests)

        question["question_worth"] = question_worth
        question["total_negated"] = total_negated
        question["last_attempt_wrong"] = last_attempt_wrong

    return questions


def add_question(quiz_id, description):
    """
    Adds a question to a quiz
    """

    query = """
    INSERT INTO questions (question_quiz_id, question_description)
    VALUES (%s, %s)
    """

    question_id = db.insert_query(query, (quiz_id, description))

    return question_id


def add_tests(question_id, test_cases):
    """
    Adds test cases for a specific problem
    """

    query = """
    INSERT INTO tests (test_question_id, test_input, test_expected)
    VALUES (%s, %s, %s)
    """
    tests = map(
        lambda test: (question_id, test["test_input"], test["test_expected"]),
        test_cases)

    db.insert_many(query, tuple(tests))


def precheck_file_name(student_id, quiz_id, question_id):
    return "code_{}_{}_{}.py".format(student_id, quiz_id, question_id)


def run_code(filepath):
    """
    Runs python code for a specific filetype and language

    Returns a tuple in format (output, is_error)

    Returns output and exit code
    """
    bashCommand = RUN_CODE_COMMAND.format(filepath)
    try:
        output = subprocess.check_output(
            bashCommand.split(), stderr=subprocess.STDOUT, timeout=3)

        return output.decode(), False
    # Gets called if python program returns an error code
    except subprocess.CalledProcessError as e:
        print(e)
        return "\n".join(e.output.decode().split("\n")[1:]), True

    # Gets called if timeout expires
    except subprocess.TimeoutExpired as e:
        return TIME_LIMIT_EXCEEDED, True


def get_test_cases(question_id):
    """
    Gets the test cases for a specific question in the quiz
    """

    query = """
    SELECT test_id, test_input, test_expected
    FROM tests 
    WHERE test_question_id = %s
    """

    test_cases = db.query(query, (question_id))

    return test_cases


def insert_attempt(question_id, student_id):
    """
    Inserts a users question attempt
    """

    query = """
    INSERT INTO attempts
    VALUES (DEFAULT, %s, %s)
    """

    attempt_id = db.insert_query(query, (question_id, student_id))

    return attempt_id


def insert_test_cases(test_case_results, attempt_id):
    """
    Inserts a users test cases into answers table 
    """
    query = """
    INSERT INTO answers
    VALUES (DEFAULT, %s, %s, %s)
    """

    for test_case in test_case_results:
        db.query(query,
                 (test_case["output"], test_case["test_id"], attempt_id))


def delete_question(quiz_id, question_id):
    """
    Deletes a question from the quiz
    """

    query = """
    DELETE FROM questions
    WHERE question_quiz_id = %s AND question_id = %s
    """

    rowcount = db.query_rowcount(query, (quiz_id, question_id))

    if rowcount != 1:
        raise ValueError("Database did not alter required field")


def get_free_quizzes():
    """
    Gets all the free quizzes
    """

    query = """
    SELECT quizzes_courses.qc_id, quizzes.quiz_name, languages.language_name, quizzes.quiz_short_desc
    FROM quizzes_courses
    INNER JOIN quizzes ON quizzes_courses.qc_quiz_id = quizzes.quiz_id
    INNER JOIN languages ON quizzes.quiz_language_id = languages.language_id
    WHERE quizzes_courses.qc_course_id IS NULL
    """

    free_quizzes = db.query(query)

    return free_quizzes


def get_languages():
    """
    Gets all supported programming languages
    """

    query = """
    SELECT *
    FROM languages
    """

    languages = db.query(query, ())

    return languages


def create_free_quiz(quiz_name, quiz_language_id, quiz_short_desc):
    """
    Checks for errors and creates a free quiz if no errors found
    """

    # Check for errors
    if not quiz_name or not quiz_language_id or not quiz_short_desc:
        raise ValueError("Property in body is empty")

    # Check types
    if type(quiz_name) != str or type(quiz_language_id) != int or type(
            quiz_short_desc) != str:
        raise ValueError("Types in body are incorrect")

    if len(quiz_name) > 20 or len(quiz_short_desc) > 20:
        raise ValueError("One field in body is too long")

    # Also check that the language_id actually exists
    query = """
    SELECT language_id
    FROM languages
    WHERE language_id = %s
    """

    languages = db.query(query, (quiz_language_id))

    if not languages:
        raise ValueError("Language ID does not exist")

    query = """
    INSERT INTO quizzes (quiz_name, quiz_language_id, quiz_short_desc)
    VALUES (%s, %s, %s)
    """

    db.insert_query(query, (quiz_name, quiz_language_id, quiz_short_desc))


def update_question_errors(question_id, question_description, test_cases):
    """
    Checks for errors with updating the questions
    """

    if not question_description or type(question_description) != str or type(
            test_cases) != list:
        return True

    if len(question_description) > 500:
        return True

    return False


def create_test_case(question_id, test_input, test_expected):
    """
    Creates a test case
    """

    if not test_input or not test_expected:
        raise ValueError("Property in body is empty")

    if type(test_input) != str or type(test_expected) != str:
        raise ValueError("test_input or test_expected were not a string")
    if len(test_input) > 500 or len(test_expected) > 500:
        raise ValueError("Length of property was too long")

    query = """
    INSERT INTO tests (test_question_id, test_input, test_expected)
    VALUES (%s, %s, %s)
    """

    test_id = db.insert_query(query, (question_id, test_input, test_expected))

    return test_id


def delete_test_case(test_id):
    """
    Deletes a test case
    """

    query = """
    DELETE FROM tests
    WHERE test_id = %s
    """

    rowcount = db.query_rowcount(query, (test_id))

    if rowcount != 1:
        raise ValueError("Less or more then 1 row was deleted")


def update_description(question_description, question_id):
    """
    Updates a description of a question 
    """

    query = """
    UPDATE questions
    SET question_description = %s
    WHERE question_id = %s
    """

    rowcount = db.query_rowcount(query, (question_description, question_id))

    if rowcount != 1:
        raise ValueError("Less or more then 1 row was updated")
