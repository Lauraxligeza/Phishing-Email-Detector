# Phishing Detector

I built a phishing detector in Python that also recognises ordinary spam. It runs locally and works in any browser. Paste in an email, click **Analyze**, and it gives you one of three predictions: legitimate, ordinary spam, or phishing/fraud.

## Data source

I downloaded the [Phishing Email Dataset from Kaggle](https://www.kaggle.com/datasets/naserabdullahalam/phishing-email-dataset). I used six files from the collection: `CEAS_08.csv`, `Enron.csv`, `Ling.csv`, `Nazario.csv`, `Nigerian_Fraud.csv`, and `SpamAssasin.csv`. That gave me **82,486 emails** to work with.

The [original dataset record on Zenodo](https://doi.org/10.5281/zenodo.8339691) lists the files and the research behind the collection by A. I. Champa, M. F. Rabbi, and M. F. Zibran.

## Running it locally

With the trained v2 model in place and the virtual environment active, run:

```bash
python check_email_web.py
```

Open the address shown in the terminal in any browser.


## Building the detector

I wrote Python scripts to inspect the emails, decode subjects and message bodies, and extract text from HTML. My first duplicate check found zero exact copies. When I ran it again after normalising whitespace, I found 592 extra copies. I grouped similar emails before splitting the data so that variations of the same message stayed together.

I started with TF-IDF and logistic regression. The first model reached 98.85% accuracy on 6,927 test emails, but the original labels grouped spam and fraud together. An ad for printer toner and a fake bank email could both count as correct predictions. I wanted my detector to tell me which one I was looking at.

For the three-category classifier, I started with 60 training emails. I compared three versions on a separate batch of 60 emails reviewed with AI assistance. We marked four as uncertain and scored the remaining 56.

| Model | What I tried | Correct out of 56 |
| --- | --- | --- |
| v1 | Whole words | 46 |
| v2 | Whole words and short character sequences | 51 |
| v3 | Same approach as v2, with nine more training emails | 46 |

The character sequences were useful for words like `viaagrra`. Even when the full spelling is unfamiliar, smaller parts of the word can still match something the model has seen before.

**I kept v2 for the first release.** It recognised 26 of 27 legitimate emails, 20 of 23 ordinary spam emails, and 5 of 6 phishing or fraud emails. When I checked where v3 had gone wrong, five spam emails that v2 had caught were now coming back as legitimate.

## One thing it got wrong

I made up a hotel called Star Hotels and wrote myself a booking confirmation. I included the dates, room type and confirmation number. The room was already booked. The only reason to reply was if I had a special request.

The detector called it phishing. I checked which words had influenced the result and found that "your" pushed the prediction towards phishing more than any other whole word in the email. Neither "reservation" nor "booking" had appeared in its whole-word training vocabulary. I later found a workshop email in the validation data confirming someone’s hotel room. It flagged that one too.

## Where I’m taking it

I’m continuing this project beyond the first release. **App v2** will be a browser extension for Gmail and Outlook. I can reuse the classifier I’ve already built and focus on extracting the selected email from a conversation. I’ll keep the paste option as well.

For **app v3**, I want to include the sender’s domain and train on a much larger, more varied collection of emails. I’m keeping the hotel examples as a check: can the next model recognise a routine reservation and still flag a message demanding card details to keep the room?