from transitions import Machine
from transitions.extensions import HierarchicalMachine as Machine  # Enable hierarchical states

class Tutor:
    states = [
        {"name": "start", "on_enter": ["welcome_message"]},
        {"name": "identify_course_goals", "on_enter": ["prompt_goals"]},
        {"name": "develop_teaching_style", "on_enter": ["suggest_styles"]},
        {"name": "plan_course_syllabus", "on_enter": ["start_syllabus"]},
        {"name": "collaborative_syllabus_design", "on_enter": ["initiate_collaboration"]},
        {"name": "teaching_methods", "on_enter": ["recommend_methods"]},
        {"name": "classroom_activities", "on_enter": ["generate_activities"]},
        {"name": "assessment", "on_enter": ["create_assessment"]},
        {"name": "feedback", "on_enter": ["request_feedback"]},
        {"name": "reflect_on_teaching", "on_enter": ["prompt_reflection"]},
        {"name": "adapt_and_improve", "on_enter": ["suggest_improvements"]},
        {"name": "support_structures", "on_enter": ["offer_support"]},
        {"name": "broadening_course_content", "on_enter": ["expand_content"]},
        {"name": "teaching_future_precollege_teachers", "on_enter": ["teacher_training"]},
        {"name": "end", "on_enter": ["exit_message"]}
    ]

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=self.states,
            initial="start",
            ignore_invalid_triggers=True  # Handle unexpected triggers gracefully
        )

        # Define transitions with potential alternate paths
        transitions = [
            # Main flow
            {"trigger": "set_goals", "source": "start", "dest": "identify_course_goals"},
            {"trigger": "develop_style", "source": "identify_course_goals", "dest": "develop_teaching_style"},
            {"trigger": "plan_syllabus", "source": "develop_teaching_style", "dest": "plan_course_syllabus"},
            {"trigger": "collaborate", "source": "plan_course_syllabus", "dest": "collaborative_syllabus_design"},
            {"trigger": "select_methods", "source": "collaborative_syllabus_design", "dest": "teaching_methods"},
            {"trigger": "prepare_activities", "source": "teaching_methods", "dest": "classroom_activities"},
            {"trigger": "assess", "source": "classroom_activities", "dest": "assessment"},
            
            # Feedback loop
            {"trigger": "gather_feedback", "source": "assessment", "dest": "feedback"},
            {"trigger": "process_feedback", "source": "feedback", "dest": "reflect_on_teaching"},
            
            # Improvement cycle
            {"trigger": "reflect", "source": "reflect_on_teaching", "dest": "adapt_and_improve"},
            {"trigger": "implement_changes", "source": "adapt_and_improve", "dest": "support_structures"},
            
            # Optional expansion paths
            {"trigger": "expand", "source": "support_structures", "dest": "broadening_course_content"},
            {"trigger": "train_teachers", "source": "broadening_course_content", "dest": "teaching_future_precollege_teachers"},
            {"trigger": "finalize", "source": "teaching_future_precollege_teachers", "dest": "end"},
            
            # Recovery paths
            {"trigger": "revise_syllabus", "source": "*", "dest": "plan_course_syllabus"},
            {"trigger": "adjust_methods", "source": "*", "dest": "teaching_methods"},
            {"trigger": "repeat_assessment", "source": "*", "dest": "assessment"},
        ]

        for transition in transitions:
            self.machine.add_transition(**transition)

    # State entry actions
    def welcome_message(self):
        print("\nWelcome to AI Tutor! Let's create your course.")

    def prompt_goals(self):
        print("\nLet's define your course goals. What outcomes do you want for your students?")

    def suggest_styles(self):
        print("\nNow developing teaching style. Consider these approaches: [list of styles]")

    def start_syllabus(self):
        print("\nStarting syllabus creation. Recommended structure: [template]")

    def initiate_collaboration(self):
        print("\nInviting collaborators to review syllabus draft...")

    def recommend_methods(self):
        print("\nSuggested teaching methods: [method1], [method2], [method3]")

    def generate_activities(self):
        print("\nGenerating classroom activities based on selected methods...")

    def create_assessment(self):
        print("\nCreating assessment tools aligned with course goals...")

    def request_feedback(self):
        print("\nGathering student feedback through surveys and evaluations...")

    def prompt_reflection(self):
        print("\nReflection phase: What worked well? What needs improvement?")

    def suggest_improvements(self):
        print("\nSuggested improvements based on feedback: [list of recommendations]")

    def offer_support(self):
        print("\nEstablishing student support structures: [resources list]")

    def expand_content(self):
        print("\nBroadening course content with interdisciplinary connections...")

    def teacher_training(self):
        print("\nDeveloping training materials for future pre-college teachers...")

    def exit_message(self):
        print("\nCourse development complete! You're ready to teach.")

    def run(self):
        print("Starting AI Tutor...")
        while True:
            if self.state == "end":
                break
            
            print(f"\nCurrent phase: {self.state.replace('_', ' ').title()}")
            
            # Get available transitions
            triggers = self.machine.get_triggers(self.state)
            print("Available actions:", ", ".join(triggers))
            
            # Simulate user input (in real implementation, use actual input)
            if self.state == "start":
                self.set_goals()
            else:
                # Auto-progress for demo purposes
                next_trigger = self.machine.get_triggers(self.state)[0]
                getattr(self, next_trigger)()

if __name__ == "__main__":
    tutor = Tutor()
    tutor.run()
