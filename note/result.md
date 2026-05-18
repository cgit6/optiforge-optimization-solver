# 4. Computational Results

In this section, several experiments were conducted to evaluate the performance of the proposed algorithm. Additionally, the proposed algorithm's effectiveness was compared with that of other competing algorithms.

## 4.1 The Development Environment of The Proposed Algorithms

The experiments were conducted on a Windows 11 computer with 32 GB of RAM and an Intel Xeon E5 1650v3 @ 3.50 GHz processor.

Each proposed algorithm was executed 20 times on the entire problem library. The algorithms were implemented using Python 3.11 in the Visual Studio Code environment.

## 4.2 Problem Sets Used

The performance of the algorithms was assessed using four classic MKP libraries, which are described in the literature and are available through the OR-Library.

Problem Set 1 includes 16 instances with `m = 2` to `30` and `n = 20` to `105`. It comprises problem instances from Sento, HP, PB, and Weing, containing 2, 2, 6, and 8 instances, respectively.

Problem Set 2 contains 30 medium-sized questions with `m = 5` and `n = 30` to `90`. These instances are labeled as Weish.

Problem Set 3 includes 30 large-scale problem instances divided into two subsets. Subset 3-1 consists of 15 instances with `m = 15` and `n ∈ {100, 250, 500}`, labeled cb1, cb2, and cb3, respectively. Subset 3-2 also consists of 15 instances with `m = 15` and `n ∈ {100, 250, 500}`, labeled cb4, cb5, and cb6, respectively.

Problem Set 4 contains nine questions with `m = {15, 25, 50}` and `n ∈ {100, 200, 500, 1000, 1500}`, labeled GK.

## Table 3. The scales of problem sets

### Problem Set 1

| Instance |  BKS |  N |  M | Instance |    BKS |  N |  M | Instance |     BKS |   N |  M |
| -------- | ---: | -: | -: | -------- | -----: | -: | -: | -------- | ------: | --: | -: |
| Sento 1  | 7772 | 60 | 30 | PB4      |  95168 | 29 |  2 | Weing3   |   95677 |  28 |  2 |
| Sento 2  | 8722 | 60 | 30 | PB5      |   2139 | 20 | 10 | Weing4   |  119337 |  28 |  2 |
| HP1      | 3418 | 28 |  4 | PB6      |    776 | 40 | 30 | Weing5   |   98796 |  28 |  2 |
| HP2      | 3186 | 35 |  4 | PB7      |   1035 | 37 | 30 | Weing6   |  130623 |  28 |  2 |
| PB1      | 3090 | 27 |  4 | Weing1   | 141278 | 28 | 30 | Weing7   | 1095445 | 105 |  2 |
| PB2      | 3186 | 34 |  4 | Weing2   | 130883 | 28 |  2 | Weing8   |  624319 | 105 |  2 |

### Problem Set 2

| Instance |  BKS |  N |  M | Instance |  BKS |  N |  M | Instance |   BKS |  N |  M |
| -------- | ---: | -: | -: | -------- | ---: | -: | -: | -------- | ----: | -: | -: |
| weish01  | 4554 | 30 |  5 | weish11  | 5643 | 50 |  5 | weish21  |  9074 | 70 |  5 |
| weish02  | 4536 | 30 |  5 | weish12  | 6339 | 50 |  5 | weish22  |  3947 | 70 |  5 |
| weish03  | 4115 | 30 |  5 | weish13  | 6159 | 50 |  5 | weish23  |  8344 | 80 |  5 |
| weish04  | 4561 | 30 |  5 | weish14  | 6954 | 60 |  5 | weish24  | 10220 | 80 |  5 |
| weish05  | 4514 | 30 |  5 | weish15  | 7436 | 60 |  5 | weish25  |  9939 | 80 |  5 |
| weish06  | 5557 | 40 |  5 | weish16  | 7289 | 60 |  5 | weish26  |  9584 | 90 |  5 |
| weish07  | 5567 | 40 |  5 | weish17  | 8633 | 60 |  5 | weish27  |  9819 | 90 |  5 |
| weish08  | 5605 | 40 |  5 | weish18  | 9580 | 70 |  5 | weish28  |  9492 | 90 |  5 |
| weish09  | 5246 | 40 |  5 | weish19  | 7698 | 70 |  5 | weish29  |  9410 | 90 |  5 |
| weish10  | 6339 | 50 |  5 | weish20  | 9450 | 70 |  5 | weish30  | 11191 | 90 |  5 |

### Problem Set 3

| Instance |   BKS |   N |  M | Instance |    BKS |   N |  M | Instance |    BKS |   N |  M |
| -------- | ----: | --: | -: | -------- | -----: | --: | -: | -------- | -----: | --: | -: |
| cb1-1    | 24381 | 100 |  5 | cb3-1    | 120148 | 500 |  5 | cb5-1    |  59187 | 250 | 10 |
| cb1-2    | 24274 | 100 |  5 | cb3-2    | 117879 | 500 |  5 | cb5-2    |  58781 | 250 | 10 |
| cb1-3    | 23551 | 100 |  5 | cb3-3    | 121131 | 500 |  5 | cb5-3    |  58097 | 250 | 10 |
| cb1-4    | 23534 | 100 |  5 | cb3-4    | 120804 | 500 |  5 | cb5-4    |  61000 | 250 | 10 |
| cb1-5    | 23991 | 100 |  5 | cb3-5    | 122319 | 500 |  5 | cb5-5    |  58092 | 250 | 10 |
| cb2-1    | 59312 | 250 |  5 | cb4-1    |  23064 | 100 | 10 | cb6-1    | 117821 | 500 | 10 |
| cb2-2    | 61472 | 250 |  5 | cb4-2    |  22801 | 100 | 10 | cb6-2    | 119249 | 500 | 10 |
| cb2-3    | 62130 | 250 |  5 | cb4-3    |  22131 | 100 | 10 | cb6-3    | 119215 | 500 | 10 |
| cb2-4    | 59463 | 250 |  5 | cb4-4    |  22772 | 100 | 10 | cb6-4    | 118829 | 500 | 10 |
| cb2-5    | 58951 | 250 |  5 | cb4-5    |  22751 | 100 | 10 | cb6-5    | 116530 | 500 | 10 |

### Problem Set 4

| Instance |  BKS |   N |  M | Instance |  BKS |   N |  M | Instance |   BKS |    N |  M |
| -------- | ---: | --: | -: | -------- | ---: | --: | -: | -------- | ----: | ---: | -: |
| GK-1     | 3766 | 100 | 15 | GK-4     | 5767 | 150 | 50 | GK-7     | 19221 |  500 | 25 |
| GK-2     | 3958 | 100 | 25 | GK-5     | 7560 | 200 | 25 | GK-8     | 18806 |  500 | 50 |
| GK-3     | 5656 | 150 | 25 | GK-6     | 7677 | 200 | 50 | GK-9     | 58089 | 1500 | 25 |

---

## 4.3 Comparison Algorithms and Evaluation Criteria

Several recent MKP algorithms from the literature were selected as competing algorithms, including:

* Hybrid learning moth search algorithm, HLMS
* SCA
* SMA
* Whale optimization algorithm, WOA
* Modified multi-verse optimization, MMVO

The results of the comparison algorithms were compiled from the relevant literature. If the result of an algorithm for a particular MKP problem instance was not available, that problem instance was excluded from the comparison.

Given that the comparison algorithms were implemented in various programming languages, executed on different computing platforms, and configured with distinct termination conditions and parameters, the average percentage deviation, PDev, was used for comparison.

Three statistical indicators were employed to evaluate the performance of the proposed algorithm against the competitors' algorithms:

* Best value
* Mean value
* Percentage deviation, PDev

PDev is a statistical measure designed to assess the error percentage between the best-known solution, BKS, and the mean of the obtained solutions. The algorithm with the lowest average PDev value is regarded as the most effective.

The PDev is calculated as follows:

```math
PDev = \frac{BKS - Mean}{BKS} \times 100\%
```

---

## 4.4 Parameter Calibration

This section examines the effects of various parameters on algorithm performance.

First, two problem instances were randomly selected from each problem set for validation, and the experimental results were summarized in Table 4.

The population was set to 20, and the termination condition was specified as 100,000 evaluations. Therefore, the maximum number of generations, `Max_iteration`, was set to:

```math
Max\_iteration = \frac{100000}{20} = 5000
```

The average PDev of each problem instance was calculated to evaluate the performance of the parameters.

Parameter combinations were tested as follows:

| Algorithm | Tested parameters                                  |
| --------- | -------------------------------------------------- |
| ISMA      | `z ∈ {0.01, 0.08, 0.15}`                           |
| ISCA      | `a ∈ {1.5, 2.0, 2.5}`                              |
| HSMSCA    | `z ∈ {0.01, 0.08, 0.15}` and `a ∈ {1.5, 2.0, 2.5}` |

The evaluation results for these algorithms with different parameter combinations across the randomly selected problem instances are presented in Appendix A, showing the best, average, and PDev values for all parameters.

The analysis concluded that:

* ISMA performed optimally with `z = 0.08`.
* ISCA performed optimally with `a = 1.5`.
* HSMSCA performed optimally with `z = 0.08` and `a = 2.5`.

The parameter `a` in ISCA has the largest impact on convergence speed, with deviations of ±0.5 from the optimal value, 1.5, causing up to a 12% increase in average PDev.

Similarly, the parameter `z` in ISMA critically affects exploration: values below 0.05 reduce solution diversity, while values above 0.10 delay convergence by over 8%.

The interaction between `z` and `a` in HSMSCA also proves essential. Maintaining `z` in `[0.08, 0.10]` and `a` in `[2.0, 2.5]` balances exploration and exploitation most effectively.

These conclusions were drawn by comparing the mean PDev values for all randomly selected problem instances.

## Table 4. The result of parameter experiments

### ISMA and ISCA

| Algorithm | Parameter value | Average PDev |
| --------- | --------------: | -----------: |
| ISMA      |      `z = 0.01` |        0.072 |
| ISMA      |      `z = 0.08` |    **0.065** |
| ISMA      |      `z = 0.15` |        0.073 |
| ISCA      |       `a = 1.5` |    **0.066** |
| ISCA      |       `a = 2.0` |        0.094 |
| ISCA      |       `a = 2.5` |        0.114 |

### HSMSCA

| Algorithm |      Parameter values | Average PDev |
| --------- | --------------------: | -----------: |
| HSMSCA    | `z = 0.01`, `a = 1.5` |        0.081 |
| HSMSCA    | `z = 0.01`, `a = 2.0` |        0.068 |
| HSMSCA    | `z = 0.01`, `a = 2.5` |        0.067 |
| HSMSCA    | `z = 0.08`, `a = 1.5` |        0.066 |
| HSMSCA    | `z = 0.08`, `a = 2.0` |        0.064 |
| HSMSCA    | `z = 0.08`, `a = 2.5` |    **0.063** |
| HSMSCA    | `z = 0.15`, `a = 1.5` |        0.067 |
| HSMSCA    | `z = 0.15`, `a = 2.0` |        0.065 |
| HSMSCA    | `z = 0.15`, `a = 2.5` |        0.071 |

---

## 4.5 The Final Results

This section compares the optimal parameter values identified in Section 4.4 with those of other state-of-the-art algorithms.

All algorithms were executed 20 times on the complete set of problem instances, with detailed performance results provided in Appendix B.

The summarized results are presented in Table 5. The ISMA, ISCA, and HSMSCA algorithms demonstrate significant advantages over the other algorithms evaluated. Furthermore, the proposed HSMSCA algorithm outperforms the others, including the ISMA and ISCA algorithms.

Table 5 lists the mean PDev values, with the best results highlighted in bold.

The validation and comparison of the proposed algorithms were conducted on 18 instances from Problem Set 1, with specific results detailed in Appendix B. The comparison metrics include the maximum value, mean value, and standard deviation percentage.

The proposed algorithm was compared with five other algorithms, HLMS, IBSMA_U1, SCA, BIWOA, and BMMVO, to evaluate Problem Set 2. The detailed performance data is shown in Table 5, where HSMSCA achieves the best solution across all 30 problems.

For Problem Set 3, Table 5 summarizes the corresponding experimental results. When compared with two other algorithms, HLMS and BIWOA, in Problem Set 3-1 and with HLMS in Problem Set 3-2, the data shows that HSMSCA slightly outperforms ISMA and ISCA and significantly outperforms other algorithms in both subsets.

For Problem Set 4, the proposed algorithms were similarly validated and compared, with the results ranked according to Max / Mean / PDev / Rank.

## Table 5. The comparison results of various algorithms

| Set |            HSMSCA |          ISMA |          ISCA |          HLMS |         BIWOA |         BMMVO |          BSCA |      IBSMA_U1 |
| --- | ----------------: | ------------: | ------------: | ------------: | ------------: | ------------: | ------------: | ------------: |
| 1   | **0.020 / 1.167** | 0.023 / 1.167 | 0.200 / 2.444 | 0.569 / 3.556 |         - / - |         - / - |         - / - |         - / - |
| 2   | **0.000 / 1.000** | 0.000 / 1.000 | 0.050 / 2.433 | 0.154 / 4.367 | 0.472 / 4.033 | 0.861 / 5.133 | 0.314 / 3.933 | 0.105 / 2.467 |
| 3-1 | **0.091 / 1.800** | 0.097 / 2.533 | 0.096 / 1.867 | 0.925 / 4.267 | 1.234 / 4.533 |         - / - |         - / - |         - / - |
| 3-2 | **0.219 / 1.800** | 0.225 / 2.333 | 0.233 / 1.933 | 1.349 / 3.933 |         - / - |         - / - |         - / - |         - / - |
| 4   | **0.180 / 1.778** | 0.182 / 2.222 | 0.188 / 2.000 | 0.922 / 5.444 | 0.857 / 5.333 | 2.438 / 8.000 | 1.997 / 7.000 | 0.624 / 4.111 |

Note: Bold value denotes the best PDev / Rank.
Note: `-` means N/A.

---

To further validate the efficacy of the HSMSCA algorithm, a series of Wilcoxon signed-rank tests were conducted.

At a confidence level of `α = 0.05`, the statistical results presented in Table 6 demonstrated that the HSMSCA algorithm exhibited significant superiority over other algorithms, including ISMA and ISCA.

## Table 6. The result of Wilcoxon signed-rank test on PDev

| Set     | Statistic |    ISMA |    ISCA |     HLMS |  BIWOA |  BMMVO |   BSCA | IBSMA_U1 |
| ------- | --------- | ------: | ------: | -------: | -----: | -----: | -----: | -------: |
| Set 1   | W value   |  79.000 |  22.500 |    0.500 |      - |      - |      - |        - |
| Set 1   | p-value   |   0.766 |   0.005 |    0.000 |      - |      - |      - |        - |
| Set 2   | W value   | 232.500 |  76.500 |    5.000 | 22.500 | 18.000 | 27.500 |   76.500 |
| Set 2   | p-value   |   1.000 |   0.001 |    0.000 |  0.000 |  0.000 |  0.000 |    0.001 |
| Set 3-1 | W value   |  21.000 |  55.500 |    0.000 |      - |  2.500 |      - |        - |
| Set 3-1 | p-value   |   0.025 |   0.803 |    0.000 |      - |  0.000 |      - |        - |
| Set 3-2 | W value   |  30.000 |  51.500 |    0.000 |      - |      - |      - |        - |
| Set 3-2 | p-value   |   0.094 |   0.638 | 0.000061 |      - |      - |      - |        - |
| Set 4   | W value   |  14.000 |  18.000 |    0.000 |  0.000 |  0.000 |  0.000 |    0.000 |
| Set 4   | p-value   |   0.359 |   0.652 |    0.003 |  0.003 |  0.003 |  0.003 |    0.003 |
| All     | W value   | 269.000 | 393.500 |    0.000 |  0.000 |  2.500 |  0.000 |    0.000 |
| All     | p-value   |   0.004 |   0.000 |    0.000 |  0.000 |  0.000 |  0.000 |    0.000 |

Note: `-` means N/A.

---

# 5. Conclusions and Future Research

This study presented a binary version of both the SMA and SCA, with a linear relaxation method applied, called ISMA and ISCA, to address the MKP problem.

A novel hybrid algorithm, HSMSCA, was developed by combining these two algorithms and incorporating a selection mechanism to optimize the solution update strategy.

The linear relaxation solution was utilized to calculate the price-performance ratio of items, which not only assessed item preferences but also effectively guided the search process, thereby significantly enhancing solution-finding efficiency.

An innovative algorithmic framework was proposed, which used a selection mechanism to determine whether to adopt the SMA or SCA for updating solutions, thus improving the algorithm’s adaptability and effectiveness.

The effectiveness of the HSMSCA algorithm was verified on four commonly used MKP problem sets, with results showing that HSMSCA outperformed the ISMA, ISCA algorithms, and other meta-heuristic algorithms.

Future research can be pursued in two primary directions.

First, the applicability of HSMSCA can be explored for other optimization problems, such as multi-objective knapsack problems or feature selection.

Second, the algorithms can be enhanced by integrating orthogonal learning, deep reinforcement learning, and adaptive learning strategies to further improve the search capabilities of the HSMSCA algorithm.

---

# Data Availability Statement

The data that support the findings of this study are available from the corresponding author upon reasonable request.

---

# Disclosure of Interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.
