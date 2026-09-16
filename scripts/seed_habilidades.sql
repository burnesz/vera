-- ==============================================================================
-- Carga Inicial: Matriz de Referência de Matemática e suas Tecnologias (ENEM)
-- 30 Habilidades (H01 a H30) distribuídas nas 7 Competências de Área do INEP
-- ==============================================================================

INSERT INTO habilidades_enem (codigo, competencia, descricao, eixo_tematico) VALUES
('H01', 1, 'Reconhecer, no contexto social, diferentes significados e representações dos números e operações.', 'Números e Operações'),
('H02', 1, 'Identificar padrões numéricos ou princípios de contagem.', 'Números e Operações'),
('H03', 1, 'Resolver situação-problema envolvendo conhecimentos numéricos.', 'Números e Operações'),
('H04', 1, 'Avaliar a razoabilidade de um resultado numérico na construção de argumentos sobre afirmações quantitativas.', 'Números e Operações'),
('H05', 1, 'Avaliar propostas de intervenção na realidade envolvendo conhecimentos numéricos.', 'Números e Operações'),

('H06', 2, 'Interpretar a localização e a movimentação de pessoas/objetos em representações bidimensionais (mapas, croquis etc.).', 'Geometria'),
('H07', 2, 'Identificar características de figuras planas ou espaciais.', 'Geometria'),
('H08', 2, 'Resolver situação-problema que envolva conhecimentos geométricos de espaço e forma.', 'Geometria'),
('H09', 2, 'Utilizar conhecimentos geométricos de espaço e forma na seleção de argumentos propostos como solução de problemas do cotidiano.', 'Geometria'),

('H10', 3, 'Identificar relações entre grandezas e unidades de medida.', 'Grandezas e Medidas'),
('H11', 3, 'Utilizar a noção de escalas na leitura de representação de situação do cotidiano.', 'Grandezas e Medidas'),
('H12', 3, 'Resolver situação-problema que envolva medidas de grandezas.', 'Grandezas e Medidas'),
('H13', 3, 'Avaliar o resultado de uma medição na construção de um argumento consistente.', 'Grandezas e Medidas'),
('H14', 3, 'Avaliar proposta de intervenção na realidade envolvendo grandezas e medidas.', 'Grandezas e Medidas'),

('H15', 4, 'Identificar a relação de dependência entre grandezas.', 'Proporcionalidade'),
('H16', 4, 'Resolver situação-problema envolvendo a variação de grandezas, direta ou inversamente proporcionais.', 'Proporcionalidade'),
('H17', 4, 'Analisar informações envolvendo a variação de grandezas como recurso para a construção de argumentação.', 'Proporcionalidade'),
('H18', 4, 'Avaliar propostas de intervenção na realidade envolvendo variação de grandezas.', 'Proporcionalidade'),

('H19', 5, 'Identificar representações algébricas que expressem a relação entre grandezas.', 'Álgebra e Funções'),
('H20', 5, 'Interpretar gráfico cartesiano que represente relações entre grandezas.', 'Álgebra e Funções'),
('H21', 5, 'Resolver situação-problema cuja modelagem envolva conhecimentos algébricos.', 'Álgebra e Funções'),
('H22', 5, 'Utilizar conhecimentos algébricos/geométricos como recurso para a construção de argumentação.', 'Álgebra e Funções'),
('H23', 5, 'Avaliar propostas de intervenção na realidade envolvendo conhecimentos algébricos.', 'Álgebra e Funções'),

('H24', 6, 'Utilizar informações expressas em gráficos ou tabelas para fazer inferências.', 'Estatística e Gráficos'),
('H25', 6, 'Resolver problema com dados apresentados em tabelas ou gráficos.', 'Estatística e Gráficos'),
('H26', 6, 'Analisar informações de tabelas ou gráficos como recurso para a construção de argumentos.', 'Estatística e Gráficos'),

('H27', 7, 'Calcular medidas de tendência central ou de dispersão de um conjunto de dados.', 'Probabilidade e Estatística'),
('H28', 7, 'Resolver situação-problema que envolva conhecimentos de estatística e probabilidade.', 'Probabilidade e Estatística'),
('H29', 7, 'Utilizar conhecimentos de estatística e probabilidade como recurso para a construção de argumentação.', 'Probabilidade e Estatística'),
('H30', 7, 'Avaliar propostas de intervenção na realidade envolvendo conhecimentos de estatística e probabilidade.', 'Probabilidade e Estatística')
ON CONFLICT (codigo) DO UPDATE 
SET competencia = EXCLUDED.competencia,
    descricao = EXCLUDED.descricao,
    eixo_tematico = EXCLUDED.eixo_tematico;
