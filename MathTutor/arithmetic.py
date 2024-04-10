import random

def generate_question():
    """Generates a random arithmetic question."""
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    operator = random.choice(['+', '-', '*', '/'])
    if operator == '/':
        # Ensure division results in whole number
        num1 = num1 * num2
    question = f"What is {num1} {operator} {num2}? "
    return question, eval(str(num1) + operator + str(num2))

def teach_arithmetic():
    """Teaches arithmetic and quizzes the user."""
    explanations = {
        '+': "To add two numbers, simply put them together.",
        '-': "To subtract one number from another, take away the smaller number from the larger one.",
        '*': "To multiply two numbers, add one of them to itself as many times as the other number indicates.",
        '/': "To divide one number by another, split it into equal parts as many times as indicated by the second number."
    }
    
    # Quiz loop
    correct_answers = {}
    while True:
        question, answer = generate_question()
        print("Question:", question)
        
        # Provide explanation if not explained before
        operator = question.split()[2]
        if operator not in correct_answers:
            print("Explanation:", explanations[operator])
            correct_answers[operator] = 0
        
        # Get user's answer
        user_answer = input("Your answer: ")
        
        # Check if answer is correct
        if user_answer.isdigit() and int(user_answer) == answer:
            print("Correct!")
            correct_answers[operator] += 1
            if correct_answers[operator] == 3:
                print(f"You've answered questions with {operator} correctly 3 times. Moving to next operator.")
                del correct_answers[operator]
        else:
            print("Incorrect. Try again.")

# Start teaching and quizzing
teach_arithmetic()
