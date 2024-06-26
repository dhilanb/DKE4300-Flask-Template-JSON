import json
import re 
import ast
import os
from flask import Flask, render_template, request
from flask_cors import CORS
import pandas as pd
import numpy as np
import nltk
from helpers.__init__ import *
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

# Set up NLTK
nltk.download('punkt')

# ROOT_PATH for linking with all your files. 
# Feel free to use a config.py or settings.py with a global export variable
os.environ['ROOT_PATH'] = os.path.abspath(os.path.join("..", os.curdir))

# Get the directory of the current script
current_directory = os.path.dirname(os.path.abspath(__file__))

# Specify the path to the JSON file relative to the current script
json_file_path = os.path.join(current_directory, 'init.json')

# Assuming your JSON data is stored in a file named 'init.json'
with open(json_file_path, 'r') as file:
    tempdf = pd.read_json(file)
    tempdf = tempdf.reset_index(drop=False)
    tempdf = tempdf.rename(columns={'index': 'ID'})
    tempdf["Review"] = tempdf["Review"].apply(str)


    df = preprocess(json_file_path)
    inv_idx = token_inverted_index(df)
    idf = compute_idf(inv_idx, len(df))
    norms = compute_doc_norms(inv_idx, idf, len(df))

# Define SVD parameters
n_components = 20  # Adjust as needed
random_state = 42  # For reproducibility

# Preprocess text for SVD
text_corpus = df['Review'].apply(lambda x: ' '.join(x))

# Compute TF-IDF matrix
tfidf_vectorizer = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf_vectorizer.fit_transform(text_corpus)

# Apply SVD
svd = TruncatedSVD(n_components=n_components, random_state=random_state)
svd_matrix = svd.fit_transform(tfidf_matrix)

app = Flask(__name__)
CORS(app)

def calculate_combined_similarity(query, doc_id, cossim):
    query_representation = svd.transform(tfidf_vectorizer.transform([query]))[0]
    doc_representation = svd_matrix[doc_id]
    
    # Calculate SVD similarity
    svd_similarity = np.dot(query_representation, doc_representation) / (np.linalg.norm(query_representation) * np.linalg.norm(doc_representation))

    # Combine cosine similarity and SVD similarity
    combined_similarity = 0.6 * cossim + 0.3 * svd_similarity + .1 * df[df["ID"] == doc_id]["Score"]/100 # Adjust weights as needed

    return combined_similarity

def sorted_combined_similarities(query):
    sorted_matches = index_search(query, inv_idx, idf, norms)
    result = []
    for cos_score, docID in sorted_matches:
        newSim = calculate_combined_similarity(query, docID, cos_score)
        result.append((float(newSim), docID))
    
    return sorted(result, reverse=True, key=lambda x: x[0])


def json_search(query, console):
    query = str(query)
    sorted_matches = sorted_combined_similarities(query)
    final_list = []

    for score, docID in sorted_matches:
        if len(final_list) == 10:
            break
        
        game_data = df.loc[df["ID"] == int(docID)]
        game_data["Similarity"] = score

        if console == "any":
            text = tempdf[tempdf["ID"]==docID]["Review"].values[0]
    
            fin_ind=text.find("[")+1
            sing_quote= text.find("\', ")
            doub_quote= text.find("\", ")
            if sing_quote > doub_quote:
                fin_ind= doub_quote
            else:
                fin_ind= sing_quote
                    
            game_data["Review"] = text[text.find("[")+1: fin_ind]
            final_list.append(game_data.iloc[0].to_dict())
        else:
            if console in game_data["Platform"].tolist()[0]:
                text = tempdf[tempdf["ID"]==docID]["Review"].values[0]
                fin_ind=text.find("[")+1
                sing_quote= text.find("\', ")
                doub_quote= text.find("\", ")
                if sing_quote > doub_quote:
                    fin_ind= doub_quote
                else:
                    fin_ind= sing_quote
                game_data["Review"] = text[text.find("[")+1:fin_ind]
                final_list.append(game_data.iloc[0].to_dict())


    if len(final_list) == 0:
        final_list.append({"Game": "No results. Please try a different query.", "Similarity": 0})

    return json.dumps(final_list)

@app.route("/")
def home():
    return render_template('base.html', title="sample html")

@app.route("/episodes")
def episodes_search():
    print(request.args)
    text = request.args.get("title")
    console = request.args.get("console")
    return json_search(text, console)

if 'DB_NAME' not in os.environ:
    app.run(debug=True, host="0.0.0.0", port=5000)
