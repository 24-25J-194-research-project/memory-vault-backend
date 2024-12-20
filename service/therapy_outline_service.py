import os

from dotenv import load_dotenv

from constant import EnvKeys
from helper import Logger
from repository import TherapyOutlineRepository
from service import MemoryService, PatientService
from model import TherapyOutline, Step
from openai import OpenAI

load_dotenv()


class TherapyOutlineService:
    def __init__(self):
        self.memory_service = MemoryService()
        self.patient_service = PatientService()
        self.therapy_outline_repository = TherapyOutlineRepository()
        self.openai = OpenAI(
            api_key=os.getenv(EnvKeys.OPENAI_API_KEY.value),
        )
        self.logger = Logger(__name__)

    def get_therapy_outline_by_memory_id(self, memory_id: str) -> TherapyOutline:
        return self.therapy_outline_repository.get_therapy_outline_by_memory_id(memory_id)

    def generate_and_save_therapy_outline(self, memory_id: str) -> str:
        self.logger.info("Generating therapy outline for memory: %s", memory_id)
        # Fetch memory details
        memory = self.memory_service.get_memory_by_id(memory_id)
        patient = self.patient_service.get_patient_by_id(memory.patient_id)

        if not memory:
            raise ValueError(f"No memory found with ID: {memory_id}")

        # Prepare input data for OpenAI
        input_data = {
            "memory_id": memory_id,
            "memory_details": memory.model_dump(by_alias=True),
            "patient_details": patient.model_dump(by_alias=True)
        }

        # Generate therapy outline using OpenAI
        outline_json = self._generate_therapy_outline(input_data)

        # Save the generated outline
        therapy_outline = TherapyOutline(
            patient_id=memory.patient_id,
            memory_id=memory_id,
            steps=[Step(**step) for step in outline_json["steps"]]
        )

        self.logger.info("Saving therapy outline for memory: %s", memory_id)
        return self.therapy_outline_repository.save_therapy_outline(therapy_outline)

    def _generate_therapy_outline(self, input_data: dict) -> dict:
        prompt = self._construct_therapy_outline_prompt(input_data)

        # Call OpenAI API
        response = self.openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are an AI assistant specializing in reminiscence therapy."}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            temperature=0.2
        )

        # Extract and validate response
        output = response.choices[0].message.content
        self.logger.info("Therapy outline generated by OpenAI: %s", output)
        return self._parse_json_output(output)

    @staticmethod
    def _construct_therapy_outline_prompt(input_data: dict) -> str:
        return f"""
        Generate a therapy outline in the following JSON format:

        {{
          "patient_id": "string",
          "memory_id": "string",
          "steps": [
            {{
              "step": "int",
              "description": "string",
              "guide": ["string", "..."],
              "type": "string (INTRODUCTION, NORMAL, CONCLUSION)",
              "media_urls": ["string", "..."],
              "script": {{
                "voice": "string (alloy, echo, fable, onyx, nova, shimmer)",
                "text": "string"
              }}
            }}
          ]
        }}

        Memory Details:
        {input_data["memory_details"]}

        Patient Details:
        {input_data["patient_details"]}

        Requirements:
        - Use the patient details and memory details to generate personalized steps and guidance.
        - Include associated media URLs for each step where applicable.
        - Follow a logical structure: introduction, main session, conclusion.
        - Provide guidance points for each step in the `guide` field.
        - Each step should include a script with:
          - A calm, relaxing, and therapist-like tone.
          - Simple and empathetic language to guide reflective thinking and encourage memories.
        - Choose one consistent voice for all steps from the following options: alloy, echo, fable, onyx, nova, shimmer.
        - Ensure the JSON format matches the provided structure.
        - Provide the output as a valid JSON object without any extra formatting or code block markers.
        """

    @staticmethod
    def _parse_json_output(output: str) -> dict:
        import json
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON output from OpenAI: {e}")


# if __name__ == '__main__':
#     service = TherapyOutlineService()
#     print(service.generate_and_save_therapy_outline("6750373dae22fe6413d7e324"))
