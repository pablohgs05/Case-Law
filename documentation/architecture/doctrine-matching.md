# Matching a decision's thesis to doctrine

How this project decides which legal scholarship to point at next to a
decision, why the score alone does not decide it, and where the quality
ceiling actually sits.

Measured on **2026-10-25** against the whole collection: 991.163 decisions,
57.439 of them carrying a thesis, and 797 open-access works from the BDJur.

> **Two meanings of "thesis", and only one is meant here.** In SCRUM-111 a
> *tese* is the legal proposition a decision settled. In the BDTD, *teses* are
> doctoral dissertations. Everything below uses the first sense — the client
> wrote "conectar as teses encontradas a artigos e materiais" and meant the
> proposition.

---

## The rule that comes before the method

**A bad suggestion is worse than no suggestion.** An article about another
subject, presented as related to the thesis, costs the reader time and costs
the tool its credibility. So the threshold is chosen to stay silent rather than
to guess, and four decisions in five receive nothing.

That is the correct result, not a failure. A procedural thesis — habeas corpus,
enforcement of judgment, a break in the chain of custody — has no substantive
subject matter to match.

---

## Why plain full-text search does not work

The subtask recommended starting with the search already in the project:
`websearch_to_tsquery` over the doctrine's title and subject, path (a) of the
card. It was tried first, and it produced noise.

A thesis is procedural prose:

> *"Não configura cerceamento de defesa o julgamento antecipado da lide (CPC,
> art. 330, I e II) de processo de ação de indenização por danos materiais e
> morais, movida por pescador profissional artesanal contra a Petrobrás,
> decorrente de impossibilidade de exercício da profissão, em virtude de
> poluição ambiental causada por derramamento de óleo."*

Turned into a query, that is 103 terms. The works that win are the ones sharing
the procedural words — and every work shares them. The first result for the
thesis above was an article on **the limitation period of workplace-accident
claims**. The relevant ones were nowhere near the top.

---

## What works: weighting by rarity in judicial prose

The fix is to weight each shared term by how rare it is **in judicial
language**, not in the doctrine collection. Measured over the 991.163 ementas:

| Term | Decisions containing it | Weight |
|---|---:|---:|
| `prov` | 195.000 (19,7%) | 0,82 |
| `sumul` | 8.008 | 1,07 |
| `dan` | 5.604 | 2,46 |
| `lid` | 598 | 3,34 |
| `ambiental` | 93 | 5,09 |
| `poluica` | 8 | 11,70 |

Procedural words are common and weigh almost nothing. Subject-matter words are
rare and weigh a lot. With this weighting, the same thesis brought back
environmental jurisdiction, liability for environmental harm, and environmental
catastrophes in the top positions.

This is path (b) of the card — subject overlap — generalised from the keywords
to the whole of title plus subject. `core.doutrina_termo` holds the weights.

**Two cuts keep the vocabulary honest.** A minimum weight of 2,0 drops any term
present in more than 13% of decisions. A minimum stem length of 4 drops
stemmer accidents: `via` links *"via adequada"* to *"terceira via"*, `ger`
links anything at all to *"gera"*.

---

## The score does not tell a good suggestion from a bad one

This is the most useful thing this subtask measured, and it contradicts the
obvious design.

Thirty decisions were read case by case. Among them, the useful suggestions
scored between **9,3 and 33,4**; the useless ones scored between **9,1 and
33,0**. The single worst suggestion in the sample — an article on unfair
commercial practices offered for a thesis about the suspensive effect of an
appeal — scored **33,0**, the second-highest score of all thirty.

**Raising the threshold would cut good and bad in the same proportion.**

What does separate them is whether the matched terms form an expression or
merely co-occur. *"litigância de má-fé"*, *"união estável"*, *"arguição de
descumprimento de preceito fundamental"* are phrases. `elaboraca` and `menor`
matching twenty words apart is a coincidence.

| | Useful (13) | Useless (18) |
|---|---:|---:|
| Mean distance between matched terms | **2,6** | **12,9** |
| Above 8 words apart | **0** | 7 |

So distance enters as a fourth condition. Cutting at 8 keeps every useful
suggestion in the sample and drops seven of the useless ones — precision
without paying recall.

---

## The threshold, and what it costs

A suggestion is stored only if all four hold:

```
nota      >= 9,0    sum of the weights of the terms thesis and work share
termos    >= 2      one word in common is a coincidence
forte     >= 4,5    at least one term that is rare in judicial prose
distancia <= 8      the matched terms sit close together in the thesis
```

| Threshold | Decisions with a suggestion | Suggestions each |
|---|---:|---:|
| nota ≥ 7,0 · forte ≥ 3,5 | 55,8% | 6,6 |
| nota ≥ 9,0 · forte ≥ 4,5 | 26,9% | 2,8 |
| **nota ≥ 9,0 · forte ≥ 4,5 · dist ≤ 8** | **20,8%** | **2,4** |
| nota ≥ 12 · forte ≥ 5,0 | 10,5% | 1,8 |

The chosen row gives **28.423 links** over **11.960 decisions**, pointing at
**557** of the 797 works.

`core.decisao_doutrina` stores only what passes, and the audit
`sugestao_acima_do_limite` fails if anything below the threshold is written —
14.719 of the candidate pairs are above the proximity cut and are refused, so
the audit is live rather than decorative.

---

## The ceiling is the collection, not the method

**797 works out of the 20.597 in the open-access collection — 3,9%.** The
BDJur's endpoint refuses automated access, so the sample was saved by hand.

Most of the useless suggestions in the thirty are not ranking failures: there
is simply no relevant work in the sample, and nothing stops the matcher from
offering the closest thing it has. *"Estudo externo em regime semiaberto"*,
*"ofício ao Caged"* and *"prescrição do PASEP"* have no counterpart among 797
works, and would very likely have one among 20.597.

**Any useful-suggestion rate measured now is a floor, and the threshold has to
be re-tuned when the full collection is harvested.**

### Where the next gain is

Ranked by what was measured, not by what is interesting to build.

1. **More of the collection.** 3,9% of it is the binding limit, and it needs no
   new technique — only the BDJur answering `bdjur@stj.jus.br`, or more pages
   saved by hand.
2. **Meaning instead of stems.** Every wrong suggestion that survives is a word
   match without a meaning match: `unic` ties *"valor único"* to *"Violência:
   única opção?"*; `digital acess conteud` ties digital counterfeiting to money
   laundering; `vontad brasil manifestaca` ties an electronic signature to
   German civil law. A stemmer cannot tell these apart and no threshold over
   its output can either. This is path (c) of the subtask — `pgvector` is
   installed and has never been used — and the card says to reach for it when
   (a) and (b) do not serve. (a) produced noise and (b) stops at 54%.
3. **The reader with legal training.** 54% is one reader's judgement, and some
   of the ratings are debatable: a thesis with five numbered items may be
   legitimately matched on its third, which this reader counted as wrong.

---

## Acceptance: the rate still needs a reader with legal training

The subtask requires the sample to be evaluated by someone in Law, as subtask
7.2 does for the thesis itself. That has not happened yet, and it is not
something this document can settle.

**A provisional read, by whoever wrote this and not by a lawyer**, over thirty
decisions — read before the proximity condition was added, so not the same
thirty listed below:

| | Before proximity | Still suggested after |
|---|---:|---:|
| Clearly useful | 13 | **13** |
| Arguable | 5 | 5 |
| Wrong | 12 | **6** |
| **Useful share** | **43%** | **54%** |

The condition removed half the wrong suggestions and none of the useful ones.
Twenty-four of the thirty decisions still receive something.

**The scalar thresholds are exhausted.** Both remaining knobs were measured
against those ratings, and both make it worse:

```
forte 4,5 -> 5,0    drops 8 of the 13 useful, and only 2 of the 6 wrong
termos 2 -> 3       drops 4 of the useful, and none of the wrong
```

The wrong suggestions that survive have a *higher* mean strongest-term weight
than the useful ones (5,54 against 5,31) and sit *closer* together (distance
1,3 against 2,6).

One more idea was tried and also fails, recorded here so it is not tried
again: requiring the matched terms to form an expression **on the work's side
too**, not only in the thesis. The intuition is sound — *"dignidade sexual"* is
a phrase in the thesis but scattered across *"Regulação da Internet e novos
desafios da proteção de direitos"*. The measurement says otherwise: mean
distance on the work's side is 2,2 for the wrong suggestions and 2,8 for the
useful ones, so the wrong ones are if anything tighter.

There is no number left to turn. What the stems can tell apart, they already
do.

The sheet is ready to be filled in. Mark the `útil?` column `sim` or `não` for
each suggestion, and the rate is the count over the total.

### 1. STJ · 944249

**Tese.** 1. O ingresso em domicílio sem mandado judicial é válido em situação de flagrante delito, desde que existam fundadas razões. 2. A alegação de uso pessoal não desclassifica a conduta de tráfico quando a quantidade e a forma de acondicionamento das drogas indicam tráfico. 3. A confissão de ser usuário […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.2 | `usuari` `drog` `trafic` | [Drogas: fora da lei e dentro do usuário](https://bdjur.stj.jus.br/handle/2011/32426), 2010 | |

### 2. STJ · 2780431

**Tese.** A decisão de inadmissibilidade do recurso especial deve ser impugnada em sua integralidade, sob pena de aplicação da Súmula n. 182 do STJ. 2. A penalidade por litigância de má-fé não se aplica na ausência de recursos manifestamente protelatórios. 3. A interposição de agravo interno não permite a ma […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 9.3 | `litiganc` `ma-f` | [A avaliação do regime jurídico da litigância de má-fé em Portugal = Evaluation of Portug](https://bdjur.stj.jus.br/handle/2011/98958), 2014 | |

### 3. STJ · 2878000

**Tese.** 1. A palavra da vítima, corroborada por outras provas, é suficiente para a condenação em crimes contra a dignidade sexual. 2. A continuidade delitiva pode ser reconhecida com base em relatos de testemunhas que indiquem a prática reiterada de abusos. 3. A medida de segurança de internação é adequada  […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 13.0 | `sexual` `dignidad` `seguranc` | [Regulação da Internet e novos desafios da proteção de direitos constitucionais: o caso d](https://bdjur.stj.jus.br/handle/2011/171192), 2018 | |
| 11.5 | `sexual` `periculos` `condenaca` | [¿Qué pueden aportar a día de hoy las teorías sobre los fundamentos y fines de la pena? R](https://bdjur.stj.jus.br/handle/2011/170725), 2019 | |
| 11.3 | `sexual` `abus` `delit` | [Irracionalidad y ausencia de evaluación legislativa en las reformas de los delitos sexua](https://bdjur.stj.jus.br/handle/2011/119666), 2017 | |

### 4. STJ · 2867419

**Tese.** 1. Não há omissão quanto ao prequestionamento dos arts. 394 e 396 do Código Civil, diante do óbice aplicado. 2. Inexiste omissão sobre a aplicação do Tema 677/STJ, porque a inadmissibilidade impediu a análise da tese repetitiva. 3. Não há omissão relativa à cessação da mora na data do depósito c […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 9.3 | `litiganc` `ma-f` | [A avaliação do regime jurídico da litigância de má-fé em Portugal = Evaluation of Portug](https://bdjur.stj.jus.br/handle/2011/98958), 2014 | |

### 5. TJDFT · 0729027-44.2025.8.07.0000

**Tese.** 1- A decisão proferida no contexto do Mutirão Carcerário, com fundamento na Portaria Conjunta TJDFT nº 133/2024, é válida mesmo sem a manifestação ministerial prévia, desde que respeitado o prazo de intimação.  2- A ausência de prejuízo concreto inviabiliza a alegação de nulidade processual, conform […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 9.8 | `carcerari` `port` | [A superlotação carcerária e a juridicidade das inspeções judiciais : o caso de Porto Nac](https://bdjur.stj.jus.br/handle/2011/186279), 2021 | |

### 6. TJDFT · 0719002-69.2025.8.07.0000

**Tese.** 1. A alegação de impenhorabilidade com base no art. 833, IV, do CPC exige comprovação inequívoca da natureza alimentar dos valores bloqueados.  2. A ausência de prova documental impede a aplicação da regra de impenhorabilidade.  3. A penhora de valores de reduzido montante não compromete o mínimo ex […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.8 | `impenhor` `penhor` `natur` | [Efetividade na execução trabalhista: admissibilidade da penhora de salários e o princípi](https://bdjur.stj.jus.br/handle/2011/165091), 2014 | |

### 7. TJDFT · 0731221-17.2025.8.07.0000

**Tese.** 1. A competência territorial em execução de título extrajudicial é relativa e não pode ser reconhecida de ofício pelo juízo. 2. O foro indicado no título como local de pagamento é critério válido de fixação de competência. 3. A eleição de foro expressa em nota promissória deve ser respeitada, salvo  […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.7 | `territorial` `ofici` `titul` | [O princípio da territorialidade e os ofícios de registro de títulos e documentos](https://bdjur.stj.jus.br/handle/2011/154444), 2013 | |

### 8. TJDFT · 0706113-17.2024.8.07.0001

**Tese.** 1. O pedido de efeito suspensivo formulado no corpo da apelação, antes da sua distribuição, é incabível por inadequação da via eleita, conforme art. 1.012, § 3º, I, do CPC."; "2. O indeferimento da petição inicial da recuperação judicial, com trânsito em julgado, impede a formação do juízo universal […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 33.0 | `desleal` `concorrenc` `merc` `livr` `consumidor` `empres` `pratic` `defes` | [Práticas comerciais desleais: um estudo da directiva 2005/29/CE](https://bdjur.stj.jus.br/handle/2011/72801), 2011 | |
| 25.0 | `concorrenc` `merc` `operaco` `livr` `empres` `defes` | [Processo de controle preventivo e repressivo de operações nos setores regulados: complem](https://bdjur.stj.jus.br/handle/2011/147358), 2020 | |
| 19.1 | `concorrenc` `intervenca` `consumidor` `financeir` `defes` | [O cartel na legislação antitruste, sua relação com o fenômeno concentracionista (meio ou](https://bdjur.stj.jus.br/handle/2011/175841), 2002 | |

### 9. TJDFT · 0746024-05.2025.8.07.0000

**Tese.** 1. A impenhorabilidade prevista no artigo 833, inciso IV, do Código de Processo Civil pode ser relativizada para garantir a efetividade da execução, desde que preservado o mínimo existencial do devedor. 2. Percentual de penhora sobre salário deve observar proporcionalidade, admitindo-se redução quan […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 20.0 | `impenhor` `penhor` `salari` `proporcional` `efet` `execuca` | [Efetividade na execução trabalhista: admissibilidade da penhora de salários e o princípi](https://bdjur.stj.jus.br/handle/2011/165091), 2014 | |
| 14.2 | `impenhor` `penhor` `salari` `execuca` | [Penhora em conta corrente](https://bdjur.stj.jus.br/handle/2011/156204), 2015 | |
| 14.2 | `impenhor` `salari` `proporcional` `efet` | [A impenhorabilidade dos salários ante os princípios da efetividade da prestação jurisdic](https://bdjur.stj.jus.br/handle/2011/43615), 2009 | |

### 10. TJDFT · 0734562-51.2025.8.07.0000

**Tese.** A expedição de ofício ao Cadastro Geral de Empregados e Desempregados (Caged), Relação Anual de Informações Sociais (Rais) e Instituto Nacional do Seguro Social (INSS) para informar a existência de vínculo empregatício do devedor depende da demonstração de sua utilidade no caso concreto”.

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 15.0 | `empregatici` `empreg` `vincul` `relaca` | [O Direito do Trabalho e a geração de empregos](https://bdjur.stj.jus.br/handle/2011/171899), 2023 | |

### 11. TJDFT · 0765238-65.2024.8.07.0016

**Tese.** 1. A crítica veiculada em rede social que utiliza metáforas ou recursos retóricos insere-se na liberdade de expressão e não configura crime de difamação quando ausente dolo específico. 2. A ausência de vício integrativo impede o acolhimento dos embargos de declaração, que não constituem via adequada […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.6 | `expressa` `social` `liberdad` | [Introdução aos fundamentos dos direitos humanos nas cortes internacionais](https://bdjur.stj.jus.br/handle/2011/18369), 2007 | |
| 10.6 | `expressa` `social` `liberdad` | [Discurso del ódio y discurso político : en defensa de la libertad de los intolerantes](https://bdjur.stj.jus.br/handle/2011/45660), 2012 | |
| 9.9 | `critic` `social` | [Acesso à justiça: notas de um direito social sob o prisma de Amartya Sen = Access to jus](https://bdjur.stj.jus.br/handle/2011/110260), 2016 | |

### 12. TJDFT · 0702339-12.2025.8.07.0011

**Tese.** É parte ilegítima para figurar no polo passivo da execução de taxas condominiais o promitente vendedor que transmite a posse do imóvel ao adquirente mediante escritura pública, quando demonstrada a ciência inequívoca do condomínio acerca da alienação, nos termos do Tema 889 do STJ.

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 14.8 | `promitent` `escritur` `poss` | [Do direito do promitente comprador](https://bdjur.stj.jus.br/handle/2011/54305), 2002 | |

### 13. TJDFT · 0741738-81.2025.8.07.0000

**Tese.** Não configura omissão apta a ensejar embargos de declaração a ausência de manifestação do acórdão sobre teses jurídicas não deduzidas no recurso originário, tampouco sobre matéria que foi expressa e fundamentadamente enfrentada no julgado; os aclaratórios não se prestam à introdução de inovações nem […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 9.5 | `inovaco` `recursal` | [Inovações no processo civil em matéria recursal: considerações sobre a Lei nº 10.352/01](https://bdjur.stj.jus.br/handle/2011/27760), 2002 | |

### 14. TJDFT · 0702315-90.2019.8.07.9000

**Tese.** A inconstitucionalidade de decisão de Juizado Especial transitada em julgado, por contrariedade a pronunciamento superveniente do Tribunal local em sede de representação de inconstitucionalidade, pode ser arguida por simples petição, em prazo equivalente ao da ação rescisória”.  10. Nesse contexto,  […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 33.4 | `fundamental` `arguica` `preceit` `control` `inconstitucional` `normat` `descumpr` `norm` `constitucional` | [A argüição de descumprimento de preceito fundamental](https://bdjur.stj.jus.br/handle/2011/27514), 2002 | |
| 26.4 | `fundamental` `arguica` `preceit` `proteca` `descumpr` `indev` `seguranc` | [Hacking e infiltração policiais em resposta ao uso de criptografia por organizações crim](https://bdjur.stj.jus.br/handle/2011/160951), 2021 | |
| 25.1 | `adpf` `fundamental` `arguica` `preceit` `descumpr` `suprem` | [Lei de Anistia: comentários à sentença do Supremo Tribunal Federal no caso da ADPF 153](https://bdjur.stj.jus.br/handle/2011/172943), 2012 | |

### 15. TJDFT · 0754109-77.2025.8.07.0000

**Tese.** 1. Incumbe ao executado comprovar a natureza impenhorável dos valores bloqueados, nos termos do art. 854, § 3º, I do CPC. 2. A alegação de origem salarial exige prova da vinculação entre o valor constrito e verba de natureza alimentar. 3. A impenhorabilidade de quantia inferior a 40 salários-mínimos […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.7 | `impenhor` `salari` `natur` | [Efetividade na execução trabalhista: admissibilidade da penhora de salários e o princípi](https://bdjur.stj.jus.br/handle/2011/165091), 2014 | |

### 16. TJDFT · 0703490-22.2019.8.07.9000

**Tese.** A inconstitucionalidade de decisão de Juizado Especial transitada em julgado, por contrariedade a pronunciamento superveniente do Tribunal local em sede de representação de inconstitucionalidade, pode ser arguida por simples petição, em prazo equivalente ao da ação rescisória”. 10. Nesse contexto, o […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 29.8 | `fundamental` `arguica` `preceit` `control` `inconstitucional` `descumpr` `norm` `constitucional` | [A argüição de descumprimento de preceito fundamental](https://bdjur.stj.jus.br/handle/2011/27514), 2002 | |
| 26.4 | `fundamental` `arguica` `preceit` `proteca` `descumpr` `indev` `seguranc` | [Hacking e infiltração policiais em resposta ao uso de criptografia por organizações crim](https://bdjur.stj.jus.br/handle/2011/160951), 2021 | |
| 25.1 | `adpf` `fundamental` `arguica` `preceit` `descumpr` `suprem` | [Lei de Anistia: comentários à sentença do Supremo Tribunal Federal no caso da ADPF 153](https://bdjur.stj.jus.br/handle/2011/172943), 2012 | |

### 17. TJDFT · 0704186-39.2026.8.07.0003

**Tese.** 1. A comprovação da mora em contratos de alienação fiduciária se satisfaz com o envio de notificação extrajudicial ao endereço indicado no contrato, sendo desnecessário o efetivo recebimento. 2. A devolução da notificação com a indicação de “ausente” não afasta a validade da constituição em mora.

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 12.0 | `fiduc` `alienaca` `contrat` | [Cláusulas abusivas nos contratos de financiamento: a jurisprudência do STJ e seus reflex](https://bdjur.stj.jus.br/handle/2011/91303), 2015 | |

### 18. TJDFT · 0711253-64.2026.8.07.0000

**Tese.** 1. A parte que requer a produção de prova pericial deve adiantar os honorários do perito, nos termos do art. 95 do CPC. 2. O rateio dos honorários periciais somente é cabível quando a prova for requerida por ambas as partes ou determinada de ofício pelo juízo. 3. A inexistência de concordância da pa […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 13.4 | `perit` `peric` `pericial` | [O problema da elaboração extroversa de perícia judicial: o "case" do exame de DNA no est](https://bdjur.stj.jus.br/handle/2011/126640), 2018 | |

### 19. TJDFT · 0701003-79.2019.8.07.9000

**Tese.** A inconstitucionalidade de decisão de Juizado Especial transitada em julgado, por contrariedade a pronunciamento superveniente do Tribunal local em sede de representação de inconstitucionalidade, pode ser arguida por simples petição, em prazo equivalente ao da ação rescisória”.  6. O STF, no julgame […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.9 | `adpf` `legislaca` `suprem` | [Lei de Anistia: comentários à sentença do Supremo Tribunal Federal no caso da ADPF 153](https://bdjur.stj.jus.br/handle/2011/172943), 2012 | |
| 9.0 | `expressa` `constitucional` `judicial` | [Introdução aos fundamentos dos direitos humanos nas cortes internacionais](https://bdjur.stj.jus.br/handle/2011/18369), 2007 | |

### 20. TJDFT · 0703537-03.2024.8.07.0017

**Tese.** 1. A ausência de reconhecimento pessoal da vítima não impede a condenação quando a autoria é demonstrada por provas autônomas, coerentes e harmônicas. 2. A confissão judicial e extrajudicial do acusado, corroborada por elementos investigativos e apreensão do bem subtraído, constitui prova suficient […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 11.5 | `investig` `roub` `veicul` | [Entre campanas, cartórios e clones : como a polícia investiga furtos e roubos de veículo](https://bdjur.stj.jus.br/handle/2011/208569), 2025 | |

### 21. TJDFT · 0707160-62.2025.8.07.0010

**Tese.** 1. Configura inovação recursal a alegação não suscitada em primeiro grau, impedindo seu conhecimento em apelação. 2. A assinatura eletrônica qualificada, com certificação ICP-Brasil e mecanismos de verificação de identidade, é válida para comprovar a manifestação de vontade em contratos bancários.  […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 12.6 | `vontad` `brasil` `manifestaca` | [A declaração de vontade na perspectiva do direito civil Alemão](https://bdjur.stj.jus.br/handle/2011/187400), 2023 | |

### 22. TJDFT · 0714445-05.2026.8.07.0000

**Tese.** Aplica-se a Lei Maria da Penha às infrações penais praticadas contra a mulher no âmbito das relações domésticas e familiares, sendo presumidas a vulnerabilidade e a hipossuficiência da vítima, independentemente da motivação dos atos ou da condição do agressor ou da ofendida. Dispositivos legais cita […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 26.0 | `penh` `11.340` `mulh` `domest` `famili` | [A relevância do Poder Judiciário como instrumento de efetividade da Lei Maria da Penha p](https://bdjur.stj.jus.br/handle/2011/101534), 2016 | |
| 25.4 | `penh` `vulner` `mulh` `domest` `famili` | [Reflexos processuais da violência de gênero, doméstica e familiar nas ações cíveis e de ](https://bdjur.stj.jus.br/handle/2011/212973), 2025 | |
| 9.7 | `vulner` `relaco` | [“Blockchain”, vulnerabilidade nas relações jurídicas negociais e a alternativa ao modelo](https://bdjur.stj.jus.br/handle/2011/139428), 2019 | |

### 23. TJDFT · 0725932-69.2026.8.07.0000

**Tese.** 1. As contrarrazões não são meio adequado para pleitear a revogação de tutela recursal concedida no agravo de instrumento. 2. Documentos juntados após a fase oportuna, sem relação com fato novo, são extemporâneos e não devem ser apreciados, nos termos dos arts. 434 e 435 do CPC. 3. A declaração de h […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 9.5 | `natural` `pesso` `relaca` | [Os direitos humanos e a emergência das catástrofes ambientais: uma relação necessária = ](https://bdjur.stj.jus.br/handle/2011/122179), 2014 | |

### 24. TJDFT · 0704029-75.2026.8.07.0000

**Tese.** 1. A ausência de comunicação acerca da alteração de endereço atrai a presunção de validade das intimações realizadas no endereço constante dos autos, nos termos do art. 274, parágrafo único, do CPC. 2. A responsabilidade dos sócios pela integralização do capital social, prevista no art. 1.052 do Cód […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.8 | `capital` `social` `unic` | [Violência: única opção? Um bispo brasileiro se interroga = Violencia: ¿única opción? Un ](https://bdjur.stj.jus.br/handle/2011/122196), 2008 | |

### 25. TJDFT · 0702909-05.2024.8.07.0020

**Tese.** 1. A efetiva instauração da fase judicial compulsória prevista no art. 104-B do CDC afasta a alegação de supressão procedimental. 2. A declaração de inconstitucionalidade da exclusão automática dos empréstimos consignados da aferição do mínimo existencial exige a renovação ou complementação da prova […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 12.7 | `global` `consumidor` `plan` | [Educação do consumidor: parente pobre das pretensas políticas de consumidores no plano g](https://bdjur.stj.jus.br/handle/2011/98584), 2016 | |

### 26. TJDFT · 0719596-49.2026.8.07.0000

**Tese.** A penhora de quotas sociais é admissível quando frustradas as tentativas de localização de outros bens, sendo desnecessária a prévia demonstração da saúde financeira da sociedade ou a avaliação econômica das quotas.

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 10.3 | `quot` `sociedad` | [Análise do caso Carlão: exploração da imagem por pessoa jurídica e a necessidade de prop](https://bdjur.stj.jus.br/handle/2011/165015), 2018 | |
| 10.3 | `quot` `sociedad` | [Regime jurídico adequado da responsabilidade societária em lançamentos tributários = App](https://bdjur.stj.jus.br/handle/2011/175587), 2023 | |
| 10.3 | `quot` `sociedad` | [O direito de empresa](https://bdjur.stj.jus.br/handle/2011/63696), 2004 | |

### 27. TJDFT · 0734646-49.2025.8.07.0001

**Tese.** 1. A comercialização não autorizada de acesso a conteúdo protegido em plataforma digital configura contrafação para os fins da Lei nº 9.610/1998, independentemente de comprovação de proveito econômico efetivo pelo contrafator. 2. Não sendo possível apurar a extensão da exploração fraudulenta em meio […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 13.6 | `digital` `acess` `conteud` | [The regulation of money laundering and corporate criminal responsibility in Spain: compl](https://bdjur.stj.jus.br/handle/2011/170325), 2022 | |
| 11.2 | `digital` `fraudulent` | [A construção do constitucionalismo digital na era da desinformação: o caso Cambridge Ana](https://bdjur.stj.jus.br/handle/2011/183426), 2023 | |

### 28. TJDFT · 0709846-08.2022.8.07.0018

**Tese.** 1. O sindicato detém ampla legitimidade extraordinária para promover, como substituto processual, o cumprimento individual de sentença coletiva, independentemente de autorização ou de procuração individual dos substituídos. 2. As pretensões executórias de fazer e de pagar oriundas do mesmo título co […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 15.2 | `extraordin` `individual` `colet` `legitim` | [Legitimidade do Ministério Público para a defesa dos direitos individuais indisponíveis,](https://bdjur.stj.jus.br/handle/2011/27373), 2007 | |

### 29. STJ · 2830333

**Tese.** 1. A decisão sobre a configuração de união estável deve observar a presença de convivência pública, contínua e duradoura e estabelecida com o objetivo de constituição de família. 2. Não é qualquer relação amorosa que caracteriza a união estável. 3. Inexiste violação dos limites da causa quando o jul […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 18.6 | `estavel` `reflex` `famil` `unia` | [União estável : reflexos na esfera penal](https://bdjur.stj.jus.br/handle/2011/20698), 1997 | |
| 13.7 | `estavel` `famil` `unia` | [Casamento e concubinato : um estudo crítico = Marriage and concubinage : a critical stud](https://bdjur.stj.jus.br/handle/2011/18163), 2001 | |
| 9.3 | `estavel` `unia` | [Casamento : incursões pelos planos da existência e da validade](https://bdjur.stj.jus.br/handle/2011/20122), 1999 | |

### 30. STJ · 2906528

**Tese.** 1. Não ocorreu a ofensa aos arts. 11, 371 e 489, §1º, do Código de Processo Civil. 2. Incide a Súmula n. 7 do STJ para obstar o reexame do conjunto fático-probatório. 3. O art. 935 do Código Civil consagra a independência das esferas civil e penal, não vinculando a responsabilidade civil ao arqu […]

| nota | casou em | obra sugerida | útil? |
|---:|---|---|---|
| 11.8 | `arquiv` `policial` `respons` | [Hacking e infiltração policiais em resposta ao uso de criptografia por organizações crim](https://bdjur.stj.jus.br/handle/2011/160951), 2021 | |


---

Praxis · Case Law — Fatec São José dos Campos com Xertica.
Subtask 9.4 da SCRUM-113. Toda medição aqui é reproduzível sobre `core.decisao`,
`core.doutrina`, `core.doutrina_termo` e `core.decisao_doutrina`.
