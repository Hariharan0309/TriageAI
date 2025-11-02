
import vertexai
from vertexai import agent_engines
import os
from dotenv import load_dotenv
import time
import matplotlib.pyplot as plt

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
AGENT_ID = f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/2064957603754016768"

remote_app = agent_engines.get(
    f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/2064957603754016768"
)
print(remote_app)


def benchmark_vertex_ai_agent(project_id, location, agent_id, test_queries, expected_responses):
    """
    Benchmarks a Vertex AI agent's performance.

    Args:
        project_id: The GCP project ID.
        location: The GCP location of the agent.
        agent_id: The ID of the Vertex AI agent.
        test_queries: A list of test queries to send to the agent.
        expected_responses: A list of lists of keywords expected in the agent's responses.

    Returns:
        A dictionary containing the benchmark report.
    """
    load_dotenv()


    # Create a new session for the benchmark test
    user_id = "benchmark_user"
    initial_state = {"user_id": user_id}
    remote_session = remote_app.create_session(user_id=user_id, state=initial_state)
    session_id = remote_session['id']

    latencies = []
    accuracies = []
    words_per_second = []
    chars_per_second = []

    for i, query in enumerate(test_queries):
        start_time = time.time()
        
        response_chunks = []
        for event in remote_app.stream_query(user_id=user_id, session_id=session_id, message=query):
            if event.get('content') and event.get('content').get('parts'):
                for part in event['content']['parts']:
                    if part.get('text'):
                        response_chunks.append(part['text'])
        
        end_time = time.time()
        latency = end_time - start_time
        latencies.append(latency)
        
        full_response = "".join(response_chunks).lower()
        
        # Check for expected keywords
        if any(keyword in full_response for keyword in expected_responses[i]):
            accuracies.append(1)
        else:
            accuracies.append(0)

        # Calculate words and characters per second
        num_words = len(full_response.split())
        num_chars = len(full_response)
        words_per_second.append(num_words / latency if latency > 0 else 0)
        chars_per_second.append(num_chars / latency if latency > 0 else 0)

    avg_latency = sum(latencies) / len(latencies)
    accuracy = sum(accuracies) / len(accuracies)
    avg_words_per_second = sum(words_per_second) / len(words_per_second)
    avg_chars_per_second = sum(chars_per_second) / len(chars_per_second)

    report = {
        "total_queries": len(test_queries),
        "accuracy_percentage": accuracy * 100,
        "average_latency_seconds": avg_latency,
        "average_words_per_second": avg_words_per_second,
        "average_chars_per_second": avg_chars_per_second,
    }

    # Plot the results
    def plot_metric(title, values, ylabel):
        plt.figure()
        plt.bar(range(len(values)), values)
        plt.xlabel("Query Index")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.savefig(f"{title.lower().replace(' ', '_')}.png")
        print(f"Chart for {title} saved as {title.lower().replace(' ', '_')}.png")

    plot_metric("Latency per Query", latencies, "Seconds")
    plot_metric("Accuracy per Query", accuracies, "Correct (1) or Incorrect (0)")
    plot_metric("Words per Second per Query", words_per_second, "Words/Second")
    plot_metric("Characters per Second per Query", chars_per_second, "Chars/Second")

    return report

if __name__ == "__main__":
    

    test_queries = [
        "My laptop won’t connect to Wi-Fi",
        "Outlook keeps freezing",
        "I can’t access the VPN",
        "Reset my system password",
    ]

    expected_responses = [
        ["wifi", "network"],
        ["outlook", "restart"],
        ["vpn", "security"],
        ["password", "reset"],
    ]

    report = benchmark_vertex_ai_agent(
        project_id=PROJECT_ID,
        location="us-central1",
        agent_id=AGENT_ID,
        test_queries=test_queries,
        expected_responses=expected_responses,
    )

    print("\n=== TRIAGEAI BENCHMARK REPORT ===")
    for k, v in report.items():
        print(f"{k}: {v}")
