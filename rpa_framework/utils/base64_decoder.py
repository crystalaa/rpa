class Base64Decoder:
    @staticmethod
    def decode_base64(e, t=False):
        def n(e):
            t_val = [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
                     -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63, 52, 53,
                     54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                     12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1, 26, 27, 28, 29, 30,
                     31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1,
                     -1]
            result = ""
            r = 0
            l = t_val
            c = len(e)
            while r < c:
                while True:
                    t_char = l[255 & ord(e[r])]
                    r += 1
                    if r >= c or t_char != -1:
                        break
                if t_char == -1:
                    break

                while True:
                    n_char = l[255 & ord(e[r])]
                    r += 1
                    if r >= c or n_char != -1:
                        break
                if n_char == -1:
                    break

                result += chr((t_char << 2) | ((48 & n_char) >> 4))

                while True:
                    if r >= c:
                        break
                    o_char = 255 & ord(e[r])
                    r += 1
                    if o_char == 61:
                        return result
                    o_char = l[o_char]
                    if o_char != -1:
                        break
                if o_char == -1:
                    break

                result += chr(((15 & n_char) << 4) | ((60 & o_char) >> 2))

                while True:
                    if r >= c:
                        break
                    a_char = 255 & ord(e[r])
                    r += 1
                    if a_char == 61:
                        return result
                    a_char = l[a_char]
                    if a_char != -1:
                        break
                if a_char == -1:
                    break

                result += chr(((3 & o_char) << 6) | a_char)

            return result

        o = n(e)
        if t is not False:
            o = Base64Decoder.utf8_to16(o)
        return o

    @staticmethod
    def utf8_to16(e):
        t = ""
        i = len(e)
        n = 0
        while n < i:
            o = ord(e[n])
            n += 1
            if (o >> 4) in [0, 1, 2, 3, 4, 5, 6, 7]:
                t += e[n - 1]
            elif (o >> 4) in [12, 13]:
                a = ord(e[n])
                n += 1
                t += chr(((31 & o) << 6) | (63 & a))
            elif (o >> 4) == 14:
                a = ord(e[n])
                n += 1
                r = ord(e[n])
                n += 1
                t += chr(((15 & o) << 12) | ((63 & a) << 6) | ((63 & r) << 0))
        return t

base64Decoder = Base64Decoder()