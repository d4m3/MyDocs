import os
from openai import OpenAI
from dotenv import find_dotenv, load_dotenv
import time
import logging
from datetime import datetime
import requests
import json
import streamlit as st

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
THREAD_ID = os.environ.get("THREAD_ID")
ASSIS_ID = os.environ.get("ASSIS_ID")

model = "gpt-4-1106-preview"

# Assistant Thread ID/Assistant ID
thread_id=THREAD_ID
assis_id=ASSIS_ID

###
# Manage st Session to not reload page, use the st chat feature

# Initialize all the sesssion
if "file_id_list" not in st.session_state:
    st.session_state.file_id_list = []

if "start_chat" not in st.session_state:
    st.session_state.start_chat = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

# FrontEnd page setup
st.set_page_config(
    page_title="Study Buddy - Chat and Learn",
    page_icon=":books:"
)

# Function defs
def upload_to_openai(filepath):
    with open(filepath, "rb") as file:
        response = client.files.create(file=file.read(),purpose="assistants")
    return response.id

# Create a sidebar to upload files
file_uploaded = st.sidebar.file_uploader(
    "Upload a file to be transformed into embeddings",
    key="file_upload"
)

# Upload file button when click to upload, 
if st.sidebar.button("Upload File"):
    if file_uploaded:
        # write binary (wb)
        with open(f"{file_uploaded.name}", "wb") as f:
            f.write(file_uploaded.getbuffer())
            # upload more than 1 file
            another_file_id = upload_to_openai(f"{file_uploaded.name}")
            st.session_state.file_id_list.append(another_file_id)
            st.sidebar.write(f"File ID:: {another_file_id}")

# Display the file ids.
if st.session_state.file_id_list:
    st.sidebar.write("Uploaded File IDs:")
    for file_id in st.session_state.file_id_list:
        st.sidebar.write(file_id)
        # Associate each file id with the current assistant
        assistant_file = client.beta.assistants.files.create(
            assistant_id=assis_id,
            file_id=file_id
        )
    
# Button to initate the chat session
if st.sidebar.button("Start Chating . . . "):
    if st.session_state.file_id_list:
        st.session_state.start_chat = True

        # Create a new thread for this chat session
        chat_thread = client.beta.threads.create()
        st.session_state.thread_id = chat_thread.id
        st.write("Thread ID:", chat_thread.id)
    else:
        st.sidebar.warning("No files found. Please upload at least 1 file to get started.")

# Define the function to process messages with citations
def process_message_with_citation(message):
    """Extract content and annotation fromt he message and format"""
    message_content = message.content[0].text
    annotations = (
        message_content.annotations if hasattr(message_content,"annotations") else []
    )
    citations = []

    # Iterate over the annotations and add footnotes
    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message_content.value = message_content.value.replace(
            annotation.text, f"[{index + 1}]"
        )

        # Gather citations based on annotation attributes
        if file_citation := getattr(annotation,"file_citation", None):
            # Retrieve the cited file details (dummy response here)
            cited_file = {
                "filename":"cryptocurrency.pdf"
            } # This should be replace with actual file retrieval
            citations.append(
                f'[{index +1}] {file_citation.quote} from {cited_file["filename"]}'
                )
        elif file_path := getattr(annotation,"file_citation", None):
            # Placeholder for file download citation
            cited_file = {
                "filename":"cryptocurrency.pdf"
            } # This should be replace with actual file retrieval
            citations.append(
                f'[{index +1}] Click [here](#) to download {cited_file["filename"]}'
                )
    # Add footnotes to the end of the message content
    full_response = message_content.value + "\n\n"+"\n".join(citations)
    return full_response
    

# The main interface . . .
st.title("Study Buddy")
st.write("Learn fast by chatting with your documents")

# Check sessions
if st.session_state.start_chat:
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4-1106-preview" # model
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Show existing message if any
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
        
    # Chat input for the user
    if prompt := st.chat_input("What's new?"):
        # Add user message to the state and display to screeen
        st.session_state.messages.append({
            "role":"user",
            "content":prompt
        })
        with st.chat_message("user"):
            st.markdown(prompt)

        # Add the user's message to the existing thread
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt
        )

        # Create a run with additional instructions
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id= assis_id,
            instructions="""Please answer the questions using the knowledge provided in the files. 
            when adding additional information, make sure to distinquish it with bold or underline text."""
        )
        # Show a "spinner" while the assistant is thinking
        with st.spinner("Wait... Generating response..."):
            while run.status != "completed":
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id= run.id
                )
            # Retrieve messages added by the assistant
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )
            # Convert messages to a list and process and display assis message
            assistant_messages_for_run = [
                message for message in messages
                if message.run_id == run.id and message.role == "assistant"
            ]
        
            for message in assistant_messages_for_run:
                full_response = process_message_with_citation(message=message)
                st.session_state.messages.append(
                    {
                    "role":"assistant",
                    "content":full_response
                    }
                )
                
                with st.chat_message("assistant"):
                    st.markdown(full_response, unsafe_allow_html=True)
    else:
        st.write("Please upload at least a file to get started by clicking on the Start Chat Button")        