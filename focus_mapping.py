def get_focus_prompt(focus_slider):
    """
    Map the focus_slider value (0-100) to a prompt string for the LLM agent call.
    0-33: Focus on learning experience
    34-67: Focus on both learning experience and teaching the concept
    68-100: Focus on teaching the concept
    """
    if focus_slider <= 33:
        return "Emphasize the journey and experience of learning this concept (e.g. It's hard to learn about eigenvalues, but you think about it in terms of transformations and it's super rewarding)"
    elif focus_slider <= 67:
        return "Balance between: focusing on both emphasizing the learning experience and clear teaching of how the concept works."
    else:
        return "Focus on clearly teaching and explaining the concept (e.g. Do a-lambda*I and find the characteristic polynomial to find the eigenvalues)."