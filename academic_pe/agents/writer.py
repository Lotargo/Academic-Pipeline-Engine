import re
import logging
from typing import Callable, Optional, Dict

from academic_pe.agents.base import BaseAgent
from academic_pe.agents.self_critique import run_self_critique
from academic_pe.core.llm import _call_provider_generate

StreamCallback = Callable[[str], None]
logger = logging.getLogger(__name__)


def run_grep(pattern: str, document_sections: Optional[Dict[str, str]]) -> str:
    if not document_sections:
        return "Grep tool error: No document content available for search."
    try:
        cleaned_pattern = pattern.strip().strip("'\"")
        regex = re.compile(cleaned_pattern, re.IGNORECASE)
    except re.error as e:
        return f"Grep tool error: Invalid regex pattern '{pattern}'. Error: {e}"

    matches = []
    for name, content in document_sections.items():
        if not content:
            continue
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if regex.search(line):
                matches.append(f"Section '{name}', line {idx}: {line}")

    if not matches:
        return f"Grep tool result: No matches found for pattern '{cleaned_pattern}'."
    return "Grep tool matches:\n" + "\n".join(matches)


class WriterAgent(BaseAgent):
    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        system_prompt = self.config.system_prompt
        
        if document_sections:
            system_prompt += (
                "\n\n[GREP TOOL AVAILABLE]\n"
                "You have access to a GREP tool to search for specific words, phrases, or patterns "
                "(such as Chinese characters or specific text snippets) across all sections of the document.\n"
                "To use the GREP tool, output exactly:\n"
                "USE_GREP: <pattern>\n"
                "where <pattern> is a case-insensitive regular expression or substring to search for.\n"
                "Do not output anything else in that turn. The system will return the matching lines with their section names and line numbers.\n"
                "You can run the GREP tool multiple times to locate all issues before generating your final response.\n"
                "When you are ready to provide your final output (e.g. the section text or REPLACE blocks), "
                "output it directly without using the GREP tool."
            )

        if context:
            system_prompt += (
                "\n\n[Context Data]\n"
                "Use the following existing content as reference. "
                "Maintain consistency in style and terminology.\n"
                f"{context}"
            )

        current_user_prompt = task_description
        max_grep_turns = 5
        response = ""

        for turn in range(max_grep_turns):
            response = _call_provider_generate(
                self.llm,
                system_prompt=system_prompt,
                user_prompt=current_user_prompt,
                model=self.config.model,
                temperature=self.config.temperature,
                on_delta=on_delta if turn == max_grep_turns - 1 else None,
            )

            # Check if response is a grep tool call
            match = re.search(r"^\s*USE_GREP:\s*(.+)$", response, re.MULTILINE | re.IGNORECASE)
            if match and document_sections:
                pattern = match.group(1).strip()
                grep_results = run_grep(pattern, document_sections)
                current_user_prompt += (
                    f"\n\n[Grep Call Turn {turn + 1}]\n"
                    f"Assistant: USE_GREP: {pattern}\n"
                    f"System: {grep_results}\n"
                    "Please analyze the search results and either call USE_GREP again or provide your final output."
                )
                logger.info("WriterAgent used GREP: %s (Results: %d chars)", pattern, len(grep_results))
            else:
                if turn > 0 and on_delta is not None:
                    on_delta(response)
                result = run_self_critique(
                    agent_name="writer",
                    config=self.config,
                    llm=self.llm,
                    task_description=task_description,
                    draft_output=response,
                    system_prompt=system_prompt,
                    context=context,
                )
                self.last_self_critique_summary = result.summary or None
                return result.output

        result = run_self_critique(
            agent_name="writer",
            config=self.config,
            llm=self.llm,
            task_description=task_description,
            draft_output=response,
            system_prompt=system_prompt,
            context=context,
        )
        self.last_self_critique_summary = result.summary or None
        return result.output


class ReviewerAgent(BaseAgent):
    _APPROVED_PATTERN = re.compile(r"^\s*APPROVED\s*$", re.IGNORECASE)

    def process(
        self,
        task_description: str,
        context: Optional[str] = None,
        on_delta: Optional[StreamCallback] = None,
        document_sections: Optional[Dict[str, str]] = None,
    ) -> str:
        system_prompt = self.config.system_prompt
        if context:
            system_prompt += f"\n\n[Text to Review]\n{context}"

        raw = self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=task_description,
            model=self.config.model,
            temperature=self.config.temperature,
        )
        return raw.strip()

    def is_approved(self, feedback: str) -> bool:
        return bool(self._APPROVED_PATTERN.match(feedback))

    def parse_reason(self, feedback: str) -> str:
        if self.is_approved(feedback):
            return ""
        match = re.match(r"REJECTED[:\s]*(.*)", feedback, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else feedback
