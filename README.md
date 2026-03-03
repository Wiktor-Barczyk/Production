Moduł automatyzuje pełny proces przygotowania zleceń produkcyjnych 
w systemie Odoo, wykorzystując komunikację poprzez XML‑RPC. 
Odpowiada za pobieranie zleceń, analizę powiązań między klientami, 
tworzenie struktury katalogów na serwerze, aktualizację zamówień sprzedaży 
oraz finalizację operacji produkcyjnych.

Stanowi warstwę integracyjną pomiędzy Odoo a środowiskiem plikowym,
eliminując ręczne czynności wykonywane przez pracowników działu produkcji
i zapewniając spójność danych między systemem a strukturą dokumentów.


Główne założenia programu:

Komunikacja z Odoo odbywa się przez XML‑RPC (moduły common i object).

Program działa interaktywnie w terminalu użytkownik wpisuje komendy.

Obsługiwane są tylko zlecenia:

-w stanie confirmed (produkcje),

-workorder „Przygotowanie produkcji” w stanie ready.

Program tworzy foldery w lokalizacji:
/home/S3-AS/TWOJDORADCA/PRODUKCJA/ZAMOWIENIA PRODUKCJI/

Struktura katalogów jest kopiowana z:
--- NARZEDZIA ---/<nazwa usługi>/.../struktura katalogów/

Program rozpoznaje klienta:

-z partnera na workorderze,

-lub z relacji partnerów (firmaosoba).

Program obsługuje powiązane zlecenia (np. rozliczenia roczne).

Program kończy workorder i dodaje wpis w chatterze z szablonu.


Najważniejsze elementy modułu:

    1. get_all_productions()
       - Pobiera wszystkie aktywne zlecenia produkcyjne w stanie "confirmed",
         z wyłączeniem produktów z działu helpdesk, TD.
       - Filtruje zlecenia posiadające aktywność "Odroczenie".
       - Zwraca listę słowników z podstawowymi danymi produkcji.

    2. get_preparation_workorders()
       - Pobiera workordery o nazwie "Przygotowanie produkcji" w stanie "ready".
       - Łączy je z odpowiadającymi im zleceniami MRP.
       - Zwraca listę ujednoliconych rekordów gotowych do dalszego przetwarzania.

    3. find_linked_orders()
       - Analizuje powiązania między klientami (np. małżonek, partner fiskalny)
         oraz sprawdza, czy istnieją inne zlecenia o tym samym origin.
       - Używane głównie przy usługach typu „rozliczenie roczne”.
       - Zwraca listę powiązanych numerów WHMO.

    4. copy_structure()
       - Wyszukuje odpowiedni szablon struktury katalogów dla danej usługi.
       - Kopiuje strukturę do nowo utworzonego folderu zlecenia.
       - Automatycznie podmienia folder „Imię Nazwisko” na nazwę klienta.
       - Zapewnia spójność dokumentacji produkcyjnej.

    5. append_whmo_to_sale_line()
       - Dopisuje numer WHMO do odpowiedniej linii zamówienia sprzedaży (SO),
         jeśli produkt zlecenia odpowiada produktowi z linii SO.
       - Zapobiega duplikacji wpisów.
       - Zwraca informację, czy operacja zakończyła się sukcesem.

    6. finish_preparation_workorder()
       - Weryfikuje poprawność przygotowania folderu (istnienie struktury, dopisanie WHMO).
       - Automatycznie kończy operację „Przygotowanie produkcji” (button_finish).
       - Zwraca status powodzenia operacji.

    7. post_message_from_template()
       - Dodaje wpis w chatterze zlecenia produkcyjnego na podstawie szablonu mailowego.
       - Używane do automatycznego informowania o rozpoczęciu produkcji.
       - Zwraca True/False w zależności od powodzenia operacji.

    8. get_client_name() / get_real_client_name()
       - Ustalają właściwą nazwę klienta na podstawie partnera z workorderu
         lub relacji partnerów (firmaosoba, małżonek, partner fiskalny).
       - Zwracają nazwę gotową do użycia w strukturze katalogów.