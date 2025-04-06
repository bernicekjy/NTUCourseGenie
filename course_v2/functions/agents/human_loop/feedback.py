import os 
from dotenv import load_dotenv
from functions.utils.llm.llm import gpt_4o_mini_azure
from functions.models.graph_states import OverallState, OutputState
from knowledge_base_manager.core.qna_manager import QnAManager
from knowledge_base_manager.core.knowledge_base_manager import KnowledgeBaseManager
from knowledge_base_manager.types import Category

# TODO: delete these temp imports
# from langchain_openai import AzureChatOpenAI


load_dotenv(override=True)

class FeedbackRetrieval:
    """
    This class is used to handle feedback from the 
    human-in-a-loop pipeline
    """
    def __init__(self):
        # Initialise all the variables needed 

        # Initialise the LLM used in QnAManager
        self.llm = gpt_4o_mini_azure()

        # TODO: ignore this, temp change
        # # Defines the instance of AzureChatOpenAI class
        # self.llm = AzureChatOpenAI(
        #     azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        #     api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        #     deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
        #     model_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_4o_NAME"),
        #     api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
        #     temperature=0,
        # )

        # Define question categories
        question_categories = [
            Category(title="ADMIN", description="Questions about deadlines, submission processes, group work policies, lab sites, or assignment logistics.", example_question="Where do I submit the mini project?"),
            Category(title="TECHNICAL", description="Questions about programming errors, technical setup, or software issues.", example_question="How do I resolve this error when installing the library?"),
            Category(title="CONTENT", description="Questions about course material, lecture content, concepts, or explanations of topics.", example_question="Can you explain the concept of dynamic programming again?"),
            Category(title="EVALUATION", description="Questions about grading criteria, marking schemes, or assessment feedback.", example_question="How many marks is the final project worth?"),
            Category(title="RESOURCE", description="Questions requesting additional resources, study materials, or sample solutions.", example_question="Do you have any sample solutions from last year’s exam?"),
            Category(title="UNCATEGORISED", description="Questions that do not clearly fit into any of the above categories.", example_question="I am confused about something but I’m not sure how to explain it."),
            Category(title="IRRELEVANT", description="Questions that are unrelated to the course or inappropriate.", example_question="What’s the best pizza place near campus?")
        ]
        

        # Initialise QnA Manager 
        self.qna_manager = QnAManager(db_connection_str=os.environ.get("FB_AZURE_COSMOSDB_CONNECTION_STR"),
            db_name = "courseGenie", # <--- change database name here
            collection_name = "qnaDocument", # <--- change collection name here
            llm=self.llm,
            rephrase_question=True,
            categorise_question=True,
            categories=question_categories)

        # Initialise Knowledge base manager 
        self.kb_manager = KnowledgeBaseManager(
            azure_text_embedding_config={
                "azure_deployment": os.environ.get("TEXT_EMBEDDING_MODEL_DEPLOYMENT"),
                "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
                "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
                "model": os.environ.get("TEXT_EMBEDDING_MODEL_NAME")
            },
            azure_ai_search_config={
                "endpoint": os.environ.get("FB_AZURE_AI_SEARCH_ENDPOINT"),
                "api_key": os.environ.get("FB_AZURE_AI_SEARCH_API_KEY")
            },
            index_name="coursegenie-qna"
        )

    def feedback(self, query: str):
        
        # Retrieve context
        docs = self.kb_manager.similarity_search(query, top_k=3)
        context = "\n".join(doc["content"] for doc in docs) # join into one string

        # Classify query: check if query can be answered with existing qna list
        response = self.classify_query(context, query)

        if "QUERY" in response: # if codeword QUERY is found, means that question couldn't be answered
            # Add question to QnA Manager
            self.qna_manager.add_unanswered_question(query)

            # Return the standard default response
            return "Sorry, I am unable to answer your question. I have forwarded your question to your course instructor."
        else:
            # Return the answer
            return response



    def classify_query(self, context_str:str, query:str):

        # Form system prompt
        system_prompt = f"""
                            You are given a context and a query. Determine whether the context provides sufficient information to answer the query.

                            If the context is enough to answer the query, respond to the query using the context.

                            If the context is insufficient to answer the query, respond with "QUERY" only.

                            Context: {context_str}
                            Query: {query}
                            """

        llm_response = self.llm.invoke(system_prompt).content

        return llm_response


    def feedback_node(self, state: OverallState) -> OverallState:
        """
        Feedback node to retrieve relevant responses
        """
        query = state.get("query")[-1]

        # Add into Database records
        feedback_output = self.feedback(query)

        return {
            "database_records": feedback_output,
            "next_action": "end",
            "steps": ["feedback_retrieval"]
        }

# TESTING ONLY, WILL DELETE LATER
if __name__ == "__main__":
    # Create an instance of FeedbackRetrieval
    feedback_retrieval = FeedbackRetrieval()

    # Test the feedback function with a sample query
    sample_query = "Can you explain the concept of dynamic programming?"
    response = feedback_retrieval.feedback(sample_query)

    # Print the response
    print("Response:", response)