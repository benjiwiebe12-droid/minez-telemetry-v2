# Notes

## How to run my solution

```bash
make up          # start Postgres + Redis
make install     # pip install -r requirements.txt
make reset-db    # apply db/02_schema.sql
make load        # publish sample data to Redis (or: make live for the streaming mode)
make worker      # in one terminal — drain the stream into Postgres
make api         # in another terminal — start the API
pytest -q        # run unit tests
```

## Design decisions

<!-- Explain the key choices you made and why. Examples to address:
  - How does your worker avoid storing duplicate events?
  - What does your consumer group setup look like, and what happens on restart?
  - How did you handle the messy data you found in the stream?
  - Why did you structure your schema the way you did?
-->

## How I handled the messy data

<!-- Describe what data quality issues you found and how your pipeline handles each one. -->

## What I'd do with more time

<!-- Stretch goals, known limitations, things you'd improve. -->

## Where I used AI tools, and for what

<!-- Be specific about what you asked for vs. what you wrote and understood yourself. -->
