# Installation & Quick Start

## Installation

```bash
pip install ai-bot-framework
```

## Quick Start

```python
from pydantic import BaseModel, Field

from ai_framework import AIApplication, BaseTool, ToolContext


class GetWeatherTool(BaseTool):
    name = "get_weather"
    description = "Get current weather for a city"

    class Input(BaseModel):
        city: str = Field(description="City name")

    def execute(self, input: Input, context: ToolContext) -> str:
        return f"Weather in {input.city}: 22C, sunny"


with AIApplication(
    api_key="sk-ant-...",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://user:pass@localhost/mydb",
    tools=[GetWeatherTool()],
) as app:
    response = app.process_message("user-123", "What's the weather in Moscow?")
    print(response.content)
```
