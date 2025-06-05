import gradio as gr
import asyncio
from main import WebScrapingOrchestrator

orchestrator = WebScrapingOrchestrator()

async def scrape_async(url):
    result = await orchestrator.process_url(url)
    if "error" in result:
        return f"❌ Error: {result['error']}"
    return {
        "URL": result.get("url"),
        "Title": result.get("title"),
        "Text Length": result["summary"]["text_length"],
        "Headings": result["llm_ready_data"]["key_headings"],
        "Main Topics": result["llm_ready_data"]["main_topics"],
        "Summary (Short)": result["llm_ready_data"]["text_summary"][:800] + "..."
    }

def scrape(url):
    return asyncio.run(scrape_async(url))

with gr.Blocks(title="MCP Web Scraper") as demo:
    gr.Markdown("### 🔍 MCP LLM Web Scraper")
    url_input = gr.Textbox(label="Enter a webpage URL", placeholder="https://...")
    output = gr.JSON(label="Scraped & LLM-ready Content")

    scrape_button = gr.Button("Scrape Page")
    scrape_button.click(scrape, inputs=url_input, outputs=output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
