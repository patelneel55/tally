from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_community.document_loaders import PyPDFLoader, AsyncHtmlLoader

def html_to_markdown(url: str) -> list[str]:
    loader = AsyncHtmlLoader(url)
    docs = loader.load()
    md_docs = MarkdownifyTransformer().transform_documents(docs)
    return md_docs

if __name__ == "__main__":
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019322000107/aapl-20221027.htm"
    md_docs = html_to_markdown(url)
    print(md_docs)