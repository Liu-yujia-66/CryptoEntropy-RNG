# Master Thesis Specification

**Uppsala University**

## Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation

| | |
|---|---|
| **Student** | Yujia Liu - yujia.liu.9362@student.uu.se |
| **Supervisor** | Andrey Shternshis - andrey.shternshis@it.uu.se |
| **Subject Reviewer** | Parosh Abdulla - Parosh.Abdulla@it.uu.se |
| **Department** | Information Technology |
| **Date** | November 7, 2025 |

---

## Table of Contents

1. [Title](#1-title)
2. [Abstract](#2-abstract)
3. [Background](#3-background)
4. [Description of Tasks](#4-description-of-tasks)
5. [Methods](#5-methods)
6. [Relevant Courses](#6-relevant-courses)
7. [Delimitations](#7-delimitations)
8. [Time Plan](#8-time-plan)

---

## 1. Title

**Random Number Generator from Aggregated Cryptocurrency Prices with an Application to Secure Password Generation**

This project explores the possibility of generating random numbers from aggregated cryptocurrency market data and applying them to secure password generation. The goal is to evaluate whether aggregated asset data can produce random sequences that meet common statistical standards for randomness.

---

## 2. Abstract

The purpose of this project is to study how financial market data can be used as a source of randomness for generating secure passwords. By aggregating price movements over different time intervals, the resulting data may show less correlation and more randomness.

The project will involve collecting data from open financial sources, transforming it into random sequences, and testing their quality using existing statistical test tools. A simple password generator prototype will then be developed to apply these sequences and evaluate their usability. The main focus will be on data analysis, evaluation, and the scientific validation of randomness, while software implementation will serve primarily for testing and demonstration.

---

## 3. Background

Random number generators (RNGs) are essential in many areas of computer science, especially in data security and encryption. Most existing RNGs are algorithmic or hardware-based. However, natural data sources — such as environmental or financial signals — can also contain random components.

Financial markets often appear unpredictable on a daily basis, but at high frequency they may show deterministic patterns. Aggregating such data over longer intervals can reduce these short-term patterns and potentially produce more random-like behavior.

This project builds on that idea by combining financial data aggregation, randomness testing, and password generation. The study belongs to the area of scientific computing within computer science: it involves computational modeling, numerical analysis, and algorithmic validation. The project's goal is to investigate the degree of randomness in financial data and evaluate their applicability in secure password generation.

### Research Questions

- How can aggregation algorithms be applied to extract statistically independent random sequences from cryptocurrency price data?
- To what extent do these sequences pass standard randomness tests?
- Can such data-driven randomness be effectively applied to secure password generation?

---

## 4. Description of Tasks

### Data Collection

- Gather open financial data from public Application Programming Interfaces (APIs) (e.g., Binance Vision).
- Organize and store data in a suitable format for analysis.

### Data Aggregation and Encoding

- Aggregate price data at multiple time intervals.
- Convert aggregated data into numerical sequences (e.g., binary or numerical encoding).

### Randomness Evaluation

- Apply standard statistical test suites (e.g., NIST SP800-22, TestU01) to the sequences.
- Examine whether aggregated data can produce outputs that appear random.

### Password Generator Prototype

- Implement a simple password generator prototype that uses the extracted random sequences.
- Test the generated passwords for distribution and strength.
- Compare the results with conventional pseudorandom generators if time permits.

### Analysis and Reporting

- Summarize and analyze results, including both strengths and limitations.
- Discuss possible improvements and future extensions.

---

## 5. Methods

The project will apply practical methods from scientific computing, data analysis, and randomness evaluation.

- **Programming Environment**: Python will be used for data collection, transformation, testing, and prototype implementation.
- **Data Aggregation**: Financial time series will be aggregated at several time scales to study how randomness changes with aggregation.
- **Testing Tools**: Randomness tests from the NIST SP800-22 and TestU01 suites will be applied to evaluate sequence quality.
- **Evaluation Metrics**: Asset prices will be evaluated by their speed of providing random sequences (in bits of entropy per day). Sequences will be analyzed through their variation and independence. The independence of random number sequences from the same asset will be measured by their mutual information i.e. by Kullback-Leibler divergence.
- **Software Implementation**: A simple password generator prototype will be developed to demonstrate and evaluate the usability of the random sequences.

Software implementation will remain limited in scope and mainly serve as a tool for validation and demonstration, taking less than one-third of the total project time.

---

## 6. Relevant Courses

- 1TD342 - Introduction to Scientific Computing
- 1TD169 - Data Engineering I
- 1TD076 - Data Engineering II
- 1DL360 - Data Mining I
- 1DL400 - Database Design II
- 1DL002 - Data, Ethics and Law

---

## 7. Delimitations

- The project does not involve market prediction, trading, or financial modeling.
- Only publicly available market data (e.g., Binance, Bybit) will be used.
- The focus is on scientific analysis of randomness and evaluation of applicability, not on large-scale software design.

---

## 8. Time Plan

The thesis work is planned over a period of approximately 20 weeks. It is divided into several main phases, starting with a literature review and ending with implementation, evaluation, and reporting.

The time allocation is approximate and may be slightly adjusted depending on progress.

| Weeks | Phase | Description |
|---|---|---|
| 1–2 | **Literature Review** | Review key studies on random number generation, financial data randomness, and statistical testing. Read and summarize the main references from the project proposal to establish the theoretical foundation and define research questions. |
| 3–6 | **Data Preparation** | Collect and process open financial market data. Apply time aggregation and organize the datasets for further analysis. |
| 7–9 | **Sequence Generation** | Transform aggregated data into random sequences and prepare them for evaluation. |
| 10–14 | **Randomness Evaluation** | Assess the generated sequences using statistical test suites such as NIST SP800-22 and TestU01. Interpret results and evaluate the quality of randomness. |
| 15–17 | **Password Generator Prototype** | Develop a simple prototype applying the extracted random sequences to password generation and perform comparative testing. |
| 18–19 | **Reporting and Presentation** | Compile and finalize the thesis report, prepare figures and results. |
| 20 | **Presentation Preparation** | Prepare and rehearse the final presentation of project outcomes. |
