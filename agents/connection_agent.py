
import re


def find_connections(evidence_documents):

    connections = []

    # Words that are not useful for identifying connections
    common_words = {
        "the", "a", "an", "is", "was", "were",
        "and", "or", "of", "to", "in", "at",
        "on", "with", "from", "by", "he", "she",
        "they", "person", "witness", "reported",
        "that", "this", "it", "near"
    }

    # Examine every pair of evidence documents
    for i in range(len(evidence_documents)):

        for j in range(i + 1, len(evidence_documents)):

            doc1 = evidence_documents[i]
            doc2 = evidence_documents[j]

            # Extract words from both documents
            words1 = set(
                re.findall(r'\b[a-zA-Z]{4,}\b', doc1["content"].lower())
            )

            words2 = set(
                re.findall(r'\b[a-zA-Z]{4,}\b', doc2["content"].lower())
            )

            # Find common meaningful words
            common = words1.intersection(words2) - common_words

            if common:

                connections.append({
                    "file1": doc1["filename"],
                    "file2": doc2["filename"],
                    "shared_words": sorted(common),
                    "description": (
                        "Both documents contain these common words: "
                        + ", ".join(sorted(common))
                    )
                })

    return connections
