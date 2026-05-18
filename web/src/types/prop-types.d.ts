declare module "prop-types" {
  export type Validator<T> = (...args: unknown[]) => Error | null;
  export type Requireable<T> = Validator<T | null | undefined> & {
    isRequired: Validator<NonNullable<T>>;
  };
  export type ValidationMap<T> = {
    [K in keyof T]?: Validator<T[K]>;
  };

  const PropTypes: Record<string, Requireable<unknown>> & {
    oneOf: (values: readonly unknown[]) => Requireable<unknown>;
    oneOfType: (types: readonly Validator<unknown>[]) => Requireable<unknown>;
    arrayOf: (type: Validator<unknown>) => Requireable<unknown[]>;
    objectOf: (type: Validator<unknown>) => Requireable<Record<string, unknown>>;
    shape: <T>(type: ValidationMap<T>) => Requireable<T>;
    exact: <T>(type: ValidationMap<T>) => Requireable<T>;
  };

  export = PropTypes;
}
