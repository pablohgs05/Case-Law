import { describe, expect, it } from 'vitest';

import { asPhone, passwordIsStrong, phoneIsComplete } from '../components/accountFormat';

/**
 * O que a caixa aceita, e o que ela conserta sozinha.
 *
 * As mesmas duas regras valem na API — isto aqui é a ajuda de quem digita, não
 * a guarda. Uma tela que só mostra a regra depois da recusa faz a pessoa
 * adivinhar; uma tela que é a única a conferir não protege nada.
 */

describe('o telefone', () => {
  it('formata enquanto se digita', () => {
    expect(asPhone('1')).toBe('1');
    expect(asPhone('12')).toBe('12');
    expect(asPhone('123')).toBe('(12) 3');
    expect(asPhone('1233334444')).toBe('(12) 3333-4444');
    expect(asPhone('12999990000')).toBe('(12) 99999-0000');
  });

  it('não deixa letra entrar', () => {
    // O que o print mostrou: `3131231231aaaa23213` digitado numa caixa livre.
    expect(asPhone('3131231231aaaa23213')).toBe('(31) 31231-2312');
    expect(asPhone('aaaa')).toBe('');
    expect(asPhone('(12) 9abc9999-0000')).toBe('(12) 99999-0000');
  });

  it('para no tamanho de um celular', () => {
    expect(asPhone('129999900001234')).toBe('(12) 99999-0000');
  });

  it('move a divisão quando vira celular', () => {
    // Em 4+4 enquanto é fixo, 5+4 quando passa de oito dígitos: senão a tela
    // mostraria `(12) 9999-90000` no meio da digitação.
    expect(asPhone('1299999000')).toBe('(12) 9999-9000');
    expect(asPhone('12999990000')).toBe('(12) 99999-0000');
  });

  it('só considera completo com dez ou onze dígitos', () => {
    expect(phoneIsComplete('')).toBe(true);
    expect(phoneIsComplete('(12) 3333-444')).toBe(false);
    expect(phoneIsComplete('(12) 3333-4444')).toBe(true);
    expect(phoneIsComplete('(12) 99999-0000')).toBe(true);
  });
});

describe('a senha', () => {
  it('exige as três coisas', () => {
    expect(passwordIsStrong('Senha123')).toBe(true);
    expect(passwordIsStrong('Senha12')).toBe(false);
    expect(passwordIsStrong('senha123')).toBe(false);
    expect(passwordIsStrong('SenhaSemNumero')).toBe(false);
  });

  it('aceita maiúscula acentuada', () => {
    // "Ática1234" começa com maiúscula, e um teste que só olhasse A-Z diria
    // que não.
    expect(passwordIsStrong('Ática1234')).toBe(true);
  });
});
