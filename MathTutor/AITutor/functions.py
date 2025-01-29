import json
from typing import Dict, Any

# Global course data structure
course_data = {
    "goals": [],
    "teaching_approaches": [],
    "selected_methods": [],
    "activities": [],
    "assessments": [],
    "improvements": [],
    "content_expansions": [],
    "training_materials": []
}

def mock_llm(prompt: str) -> str:
    """Simulate LLM response with example outputs"""
    examples = {
        "develop_teaching_style": json.dumps({
            "approaches": [
                {
                    "name": "Flipped Classroom",
                    "description": "Students review materials before class",
                    "best_for": "Applied learning objectives"
                }
            ]
        }),
        "recommend_methods": json.dumps({
            "methods": [
                {
                    "name": "Socratic Method",
                    "implementation": "Question-driven discussions",
                    "tools": ["Discussion prompts", "Case studies"]
                }
            ]
        })
    }
    return examples.get(prompt.split(":")[0], '{"error": "No response"}')

def develop_teaching_style(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate pedagogical approaches based on course goals"""
    prompt = f"""
    develop_teaching_style: Suggest 3 pedagogical approaches for these course goals:
    {course_data.get('goals', [])}
    Return JSON with "approaches" array containing objects with:
    - name (string)
    - description (string)
    - best_for (string)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "approaches" in response:
        course_data["teaching_approaches"] = response["approaches"]
        print("Generated teaching approaches:", len(response["approaches"]))
    return response

def recommend_methods(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Propose teaching methodologies based on teaching style"""
    prompt = f"""
    recommend_methods: Recommend 5 teaching methods for:
    - Style: {course_data.get('teaching_style', '')}
    - Goals: {course_data.get('goals', [])}
    Return JSON with "methods" array containing objects with:
    - name (string)
    - implementation (string)
    - tools (array of strings)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "methods" in response:
        course_data["teaching_methods"] = response["methods"]
        print("Generated teaching methods:", len(response["methods"]))
    return response

def generate_activities(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create classroom activity ideas for selected methods"""
    prompt = f"""
    generate_activities: Create 3 activities combining:
    - Methods: {course_data.get('selected_methods', [])}
    - Goals: {course_data.get('goals', [])}
    Return JSON with "activities" array containing objects with:
    - name (string)
    - duration (string)
    - materials (array)
    - learning_outcomes (array)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "activities" in response:
        course_data["activities"].extend(response["activities"])
        print("Generated activities:", len(response["activities"]))
    return response

def create_assessment(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Design evaluation framework aligned with goals"""
    prompt = f"""
    create_assessment: Create assessment framework for:
    - Course goals: {course_data.get('goals', [])}
    - Teaching methods: {course_data.get('selected_methods', [])}
    Return JSON with "assessments" array containing objects with:
    - type (string)
    - frequency (string)
    - criteria (array)
    - alignment (array of goal indices)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "assessments" in response:
        course_data["assessments"] = response["assessments"]
        print("Created assessments:", len(response["assessments"]))
    return response

def suggest_improvements(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate improvement recommendations based on feedback"""
    prompt = f"""
    suggest_improvements: Analyze this course data:
    - Feedback: {course_data.get('feedback', [])}
    - Assessment results: {course_data.get('assessment_results', [])}
    Return JSON with "improvements" array containing objects with:
    - area (string)
    - recommendation (string)
    - priority (high/medium/low)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "improvements" in response:
        course_data["improvements"] = response["improvements"]
        print("Suggested improvements:", len(response["improvements"]))
    return response

def expand_content(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Identify interdisciplinary connections"""
    prompt = f"""
    expand_content: Expand course content by connecting to:
    - Core topics: {course_data.get('core_topics', [])}
    - Related disciplines: {course_data.get('related_fields', [])}
    Return JSON with "connections" array containing objects with:
    - core_topic (string)
    - related_field (string)
    - connection_type (string)
    - resources (array)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "connections" in response:
        course_data["content_expansions"] = response["connections"]
        print("Identified connections:", len(response["connections"]))
    return response

def teacher_training(course_data: Dict[str, Any]) -> Dict[str, Any]:
    """Develop training materials for teachers"""
    prompt = f"""
    teacher_training: Create training materials covering:
    - Core content: {course_data.get('core_topics', [])}
    - Teaching methods: {course_data.get('selected_methods', [])}
    Return JSON with "materials" array containing objects with:
    - module_name (string)
    - objectives (array)
    - format (video/text/interactive)
    - duration_min (number)
    """
    
    response = json.loads(mock_llm(prompt))
    
    if "materials" in response:
        course_data["training_materials"] = response["materials"]
        print("Developed training modules:", len(response["materials"]))
    return response

# Example usage
if __name__ == "__main__":
    # Initialize with sample data
    course_data["goals"] = ["Understand OOP principles", "Develop debugging skills"]
    
    # Simulate workflow
    develop_teaching_style(course_data)
    recommend_methods(course_data)
    generate_activities(course_data)
    
    print("\nFinal course data structure:")
    print(json.dumps(course_data, indent=2))
