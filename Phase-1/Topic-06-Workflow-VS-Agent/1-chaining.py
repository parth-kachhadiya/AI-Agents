from shared_setup import Ask


def chaining(product_name : str):
    tagline = Ask(f"Write a one-line tagline for `{product_name}` product. Reply with only the tagline. tagline should be more than 100 characters.")
    
    if len(tagline) > 100:
        print("⚙️ Decision maker called.")
        print(f"[PREVIOUS-TAGLINE] : {tagline}")
        tagline = Ask(f"Shorten to under 10 words. Reply with only the result: {tagline}")

    return tagline

final_tagline = chaining("cooker")
print(f"[FINAL-TAGLINE] : {final_tagline}")